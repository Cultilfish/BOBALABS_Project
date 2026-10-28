"""Conversation helpers: parse the raw dataset into training examples and
normalise API input into one canonical shape.

Canonical message: {"role": "client" | "consultant", "message": str}
History is always stored oldest-first inside this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROLE_BY_DIRECTION = {"in": "client", "out": "consultant"}
NON_TEXT_PLACEHOLDER = "[client sent an attachment / non-text message]"


@dataclass
class Example:
    """One training example: what the client just said, what came before,
    and what the real consultant replied."""

    contact_id: str
    scenario: str
    client_sequence: list[str]
    chat_history: list[dict] = field(default_factory=list)  # oldest first
    consultant_reply: str = ""

    def to_api_payload(self) -> dict:
        return {
            "clientSequence": self.client_sequence,
            "chatHistory": self.chat_history,
            "consultantReply": self.consultant_reply,
        }


def _clean(text: str) -> str:
    text = (text or "").strip()
    if text == "[Non-text message]":
        return NON_TEXT_PLACEHOLDER
    return text


def group_into_sequences(messages: list[dict]) -> list[dict]:
    """Merge consecutive messages from the same side into one sequence.

    Returns [{"role": ..., "messages": [str, ...]}, ...] in time order.
    """
    ordered = sorted(messages, key=lambda m: (m.get("timestamp", 0), m.get("message_id", 0)))
    sequences: list[dict] = []
    for m in ordered:
        role = ROLE_BY_DIRECTION.get(m.get("direction"))
        if role is None:
            continue
        text = _clean(m.get("text", ""))
        if not text:
            continue
        if sequences and sequences[-1]["role"] == role:
            sequences[-1]["messages"].append(text)
        else:
            sequences.append({"role": role, "messages": [text]})
    return sequences


def build_examples(conversations: list[dict]) -> list[Example]:
    """Every client sequence that is followed by a consultant sequence becomes
    one Example. Client sequences with no reply (drop-offs) are skipped here
    and counted by scripts/analyze_data.py instead."""
    examples: list[Example] = []
    for conv in conversations:
        seqs = group_into_sequences(conv.get("conversation", []))
        history: list[dict] = []
        for i, seq in enumerate(seqs):
            nxt = seqs[i + 1] if i + 1 < len(seqs) else None
            if seq["role"] == "client" and nxt and nxt["role"] == "consultant":
                examples.append(
                    Example(
                        contact_id=conv.get("contact_id", ""),
                        scenario=conv.get("scenario", ""),
                        client_sequence=list(seq["messages"]),
                        chat_history=list(history),
                        consultant_reply="\n\n".join(nxt["messages"]),
                    )
                )
            for msg in seq["messages"]:
                history.append({"role": seq["role"], "message": msg})
    return examples


def load_conversations(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def split_by_contact(examples: list[Example], test_ids: set[str]) -> tuple[list[Example], list[Example]]:
    """Split by conversation, not by example, so the eval never sees a
    conversation the prompt was trained on."""
    train = [e for e in examples if e.contact_id not in test_ids]
    test = [e for e in examples if e.contact_id in test_ids]
    return train, test


# ---------------------------------------------------------------------------
# API input normalisation
# ---------------------------------------------------------------------------

class InputError(ValueError):
    pass


def normalise_client_sequence(value) -> list[str]:
    """Accept a single string or a list of strings (1+ client messages)."""
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        items = value
    else:
        raise InputError("clientSequence must be a string or a list of strings")
    items = [v.strip() for v in items if v and v.strip()]
    if not items:
        raise InputError("clientSequence must contain at least one non-empty message")
    return items


def normalise_history(value, order: str = "oldest_first") -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise InputError("chatHistory must be a list")
    if order not in ("oldest_first", "newest_first"):
        raise InputError("historyOrder must be 'oldest_first' or 'newest_first'")
    out = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise InputError(f"chatHistory[{i}] must be an object")
        role = str(item.get("role", "")).lower().strip()
        if role in ("user", "customer"):
            role = "client"
        if role in ("assistant", "agent", "ai"):
            role = "consultant"
        if role not in ("client", "consultant"):
            raise InputError(f"chatHistory[{i}].role must be 'client' or 'consultant'")
        msg = item.get("message", item.get("text"))
        if not isinstance(msg, str) or not msg.strip():
            raise InputError(f"chatHistory[{i}].message must be a non-empty string")
        out.append({"role": role, "message": _clean(msg)})
    if order == "newest_first":
        out.reverse()
    return out


def format_transcript(history: list[dict], client_sequence: list[str]) -> str:
    """Render history + the new client messages as plain text for the LLM."""
    lines = []
    if history:
        lines.append("CHAT HISTORY (oldest first):")
        for h in history:
            who = "CLIENT" if h["role"] == "client" else "CONSULTANT"
            lines.append(f"[{who}] {h['message']}")
    else:
        lines.append("CHAT HISTORY: (none - this is the start of the conversation)")
    lines.append("")
    lines.append("NEW CLIENT MESSAGE(S) TO REPLY TO:")
    for msg in client_sequence:
        lines.append(f"[CLIENT] {msg}")
    return "\n".join(lines)
