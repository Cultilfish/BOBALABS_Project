"""Core logic: generate replies, and improve the prompt from examples or
from reviewer instructions. Flask routes and scripts both call these."""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .conversation import format_transcript
from .llm import LLMClient
from .store import REPLY_PROMPT, PromptStore

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# The editable prompt (in the DB) only describes behaviour, tone and facts.
# The output contract lives here in code, so a self-edit can never break
# JSON parsing. This is the first guardrail.
OUTPUT_CONTRACT = """

## Output format (fixed, not part of the editable prompt)
Return ONLY a JSON object: {"reply": "<the exact message to send the client>"}
- The reply is plain chat text. Line breaks are allowed and numbered lists use "1." style.
- No markdown headings, bold or code fences inside the reply.
- If the client sent several messages, answer all of them in one reply."""

MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "12000"))
PLACEHOLDER_RE = re.compile(r"\[[A-Z][A-Z_]{2,}\]")  # e.g. [APP_LINK], [EMAIL]
FORBIDDEN_RULES = [
    # Things the bot must never be taught, even if a human consultant did them.
    re.compile(r"\bI (can )?(see|found|checked) your account\b", re.I),
    re.compile(r"\bpayment (has been )?received\b", re.I),
    re.compile(r"\bdon'?t (mention|tell|disclose)\b.*\b(embassy|immigration)\b", re.I),
]


def _load(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


@dataclass
class GuardrailResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def check_prompt_edit(old: str, new: str, strict: bool = True) -> GuardrailResult:
    """Reject self-edits that look like drift, truncation or bad lessons.

    strict=True for automatic edits (from examples); manual reviewer edits
    are trusted more and may restructure or shrink the prompt.
    """
    reasons = []
    if len(new.strip()) < 200:
        reasons.append("new prompt is empty or too short")
    if len(new) > MAX_PROMPT_CHARS:
        reasons.append(f"new prompt exceeds {MAX_PROMPT_CHARS} characters")
    if PLACEHOLDER_RE.search(new) and not PLACEHOLDER_RE.search(old):
        reasons.append("new prompt contains a placeholder token copied from the data")
    for pat in FORBIDDEN_RULES:
        if pat.search(new) and not pat.search(old):
            reasons.append(f"new prompt contains a forbidden rule matching /{pat.pattern}/")
    if strict:
        if len(new) > len(old) * 1.25 + 400:
            reasons.append("prompt grew too much in a single automatic edit (possible overfitting)")
        if len(new) < len(old) * 0.7:
            reasons.append("prompt shrank by over 30% (possible truncation)")
        old_heads = re.findall(r"^## .+$", old, re.M)
        missing = [h for h in old_heads if h not in new]
        if missing:
            reasons.append(f"section headings removed: {missing}")
    return GuardrailResult(ok=not reasons, reasons=reasons)


def prompt_diff(old: str, new: str) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile="current", tofile="proposed", n=1))


class Assistant:
    def __init__(self, store: PromptStore, llm: LLMClient):
        self.store = store
        self.llm = llm
        self.editor_example = _load("editor_from_example.md")
        self.editor_manual = _load("editor_from_instructions.md")

    # ---------------------------------------------------------------- reply
    def generate_reply(self, client_sequence: list[str], history: list[dict],
                       prompt_text: str | None = None) -> tuple[str, int | None]:
        version = None
        if prompt_text is None:
            pv = self.store.get_active(REPLY_PROMPT)
            prompt_text, version = pv.content, pv.version
        out = self.llm.complete_json(
            system=prompt_text + OUTPUT_CONTRACT,
            user=format_transcript(history, client_sequence),
            temperature=0.5,
            max_tokens=1024,
        )
        reply = out.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("Model response had no 'reply' text")
        return reply.strip(), version

    # ------------------------------------------------------ improve: example
    def improve_from_example(self, client_sequence, history, consultant_reply, dry_run=False) -> dict:
        current = self.store.get_active(REPLY_PROMPT)
        predicted, _ = self.generate_reply(client_sequence, history, current.content)

        user = (
            "CURRENT PROMPT:\n" + current.content
            + "\n\n=== CONVERSATION ===\n" + format_transcript(history, client_sequence)
            + "\n\n=== REAL CONSULTANT REPLY ===\n" + consultant_reply
            + "\n\n=== PREDICTED BOT REPLY ===\n" + predicted
        )
        edit = self.llm.complete_json(self.editor_example, user, temperature=0.2, max_tokens=8192)
        return self._apply_edit(current, edit, source="auto", strict=True, dry_run=dry_run,
                                extra={"predictedReply": predicted},
                                metadata={"clientSequence": client_sequence[:3],
                                          "consultantReply": consultant_reply[:500],
                                          "predictedReply": predicted[:500]})

    # ------------------------------------------------- improve: instructions
    def improve_manually(self, instructions: str, dry_run=False) -> dict:
        current = self.store.get_active(REPLY_PROMPT)
        user = "CURRENT PROMPT:\n" + current.content + "\n\n=== INSTRUCTIONS ===\n" + instructions
        edit = self.llm.complete_json(self.editor_manual, user, temperature=0.2, max_tokens=8192)
        return self._apply_edit(current, edit, source="manual", strict=False, dry_run=dry_run,
                                extra={}, metadata={"instructions": instructions[:1000]})

    # --------------------------------------------------------------- shared
    def _apply_edit(self, current, edit: dict, source, strict, dry_run, extra, metadata) -> dict:
        new_prompt = edit.get("prompt")
        summary = str(edit.get("changeSummary", "")).strip()
        result = {
            **extra,
            "diagnosis": edit.get("diagnosis"),
            "changeSummary": summary,
            "previousVersion": current.version,
        }
        if not isinstance(new_prompt, str):
            return {**result, "updated": False, "updatedPrompt": current.content,
                    "version": current.version, "rejectedReasons": ["editor returned no prompt"]}

        new_prompt = new_prompt.strip() + "\n"
        if new_prompt.strip() == current.content.strip() or summary.lower() == "no change":
            return {**result, "updated": False, "updatedPrompt": current.content,
                    "version": current.version, "diff": ""}

        check = check_prompt_edit(current.content, new_prompt, strict=strict)
        diff = prompt_diff(current.content, new_prompt)
        if not check.ok:
            return {**result, "updated": False, "updatedPrompt": current.content,
                    "version": current.version, "rejectedReasons": check.reasons,
                    "proposedDiff": diff}
        if dry_run:
            return {**result, "updated": False, "dryRun": True, "updatedPrompt": new_prompt,
                    "version": current.version, "diff": diff}

        saved = self.store.save(REPLY_PROMPT, new_prompt, source, summary,
                                {**metadata, "diagnosis": edit.get("diagnosis")})
        return {**result, "updated": True, "updatedPrompt": saved.content,
                "version": saved.version, "diff": diff}
