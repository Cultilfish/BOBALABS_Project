"""Before/after evaluation on held-out conversations.

For each prompt version given, generate replies for the same held-out
examples, score them against the real consultant reply with an LLM judge,
and write docs/BEFORE_AFTER.md with a summary table, worked examples and
the prompt diff.

Usage:
  python scripts/evaluate.py --versions 1 7 --n 12
  python scripts/evaluate.py --versions 1 latest --n 12

Set JUDGE_PROVIDER / JUDGE_MODEL to judge with a different model from the
one generating replies (reduces self-preference bias).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import time

from common import ROOT, load_split, make_assistant, spread

from app.assistant import prompt_diff
from app.conversation import format_transcript
from app.llm import LLMClient
from app.store import REPLY_PROMPT

DIMS = ["content", "nextStep", "style", "human", "overall"]
AI_ISMS = re.compile(r"happy to (help|assist)|great question|certainly!|as an ai|i hope this helps", re.I)


def judge(llm: LLMClient, system: str, ex, reply: str) -> dict:
    user = (format_transcript(ex.chat_history, ex.client_sequence)
            + "\n\n=== REAL CONSULTANT REPLY ===\n" + ex.consultant_reply
            + "\n\n=== BOT REPLY ===\n" + reply)
    s = llm.complete_json(system, user, temperature=0.0, max_tokens=512)
    return {d: float(s.get(d, 0)) for d in DIMS} | {"reason": s.get("reason", "")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", required=True, help="prompt versions, e.g. 1 latest")
    ap.add_argument("--n", type=int, default=12, help="held-out examples to score")
    args = ap.parse_args()

    assistant = make_assistant()
    store = assistant.store
    latest = store.get_active(REPLY_PROMPT).version
    versions = [latest if v == "latest" else int(v) for v in args.versions]
    prompts = {}
    for v in versions:
        pv = store.get(REPLY_PROMPT, v)
        if pv is None:
            raise SystemExit(f"Prompt version {v} not found")
        prompts[v] = pv.content

    judge_llm = LLMClient(provider=os.getenv("JUDGE_PROVIDER") or None, model=os.getenv("JUDGE_MODEL") or None)
    judge_system = (ROOT / "prompts" / "judge.md").read_text(encoding="utf-8")

    _, test = load_split()
    examples = spread(test, args.n)
    print(f"Evaluating versions {versions} on {len(examples)} held-out examples "
          f"(judge: {judge_llm.provider}/{judge_llm.model})\n")

    rows = []
    for i, ex in enumerate(examples, 1):
        row = {"contact": ex.contact_id, "client": ex.client_sequence,
               "consultant": ex.consultant_reply, "byVersion": {}}
        for v in versions:
            try:
                reply, _ = assistant.generate_reply(ex.client_sequence, ex.chat_history, prompts[v])
                scores = judge(judge_llm, judge_system, ex, reply)
            except Exception as e:
                print(f"  [{i}] v{v} ERROR {e}")
                continue
            scores["words"] = len(reply.split())
            scores["aiIsms"] = len(AI_ISMS.findall(reply))
            row["byVersion"][v] = {"reply": reply, **scores}
        rows.append(row)
        summary = "  ".join(f"v{v}={row['byVersion'][v]['overall']:.0f}" for v in versions if v in row["byVersion"])
        print(f"[{i}/{len(examples)}] {ex.contact_id}  {summary}")

    # ---- aggregate ------------------------------------------------------
    def mean(v, key):
        vals = [r["byVersion"][v][key] for r in rows if v in r["byVersion"]]
        return statistics.mean(vals) if vals else float("nan")

    human_words = statistics.median(len(r["consultant"].split()) for r in rows)
    table = ["| Metric | " + " | ".join(f"v{v}" for v in versions) + " |",
             "|---|" + "---|" * len(versions)]
    for d in DIMS:
        table.append(f"| {d} (1-5) | " + " | ".join(f"{mean(v, d):.2f}" for v in versions) + " |")
    table.append("| median words (human: %d) | " % human_words
                 + " | ".join(f"{statistics.median([r['byVersion'][v]['words'] for r in rows if v in r['byVersion']]):.0f}" for v in versions) + " |")
    table.append("| AI-ish phrases (total) | "
                 + " | ".join(f"{sum(r['byVersion'][v]['aiIsms'] for r in rows if v in r['byVersion'])}" for v in versions) + " |")
    print("\n" + "\n".join(table))

    ts = int(time.time())
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"eval_{ts}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))

    # ---- report -----------------------------------------------------------
    first, last = versions[0], versions[-1]
    scored = [r for r in rows if first in r["byVersion"] and last in r["byVersion"]]
    scored.sort(key=lambda r: r["byVersion"][last]["overall"] - r["byVersion"][first]["overall"], reverse=True)
    picks = scored[:2] + (scored[-1:] if len(scored) > 2 else [])

    md = [f"# Before / after evaluation (prompt v{first} vs v{last})", "",
          f"Generated by `scripts/evaluate.py` on {time.strftime('%Y-%m-%d %H:%M')}. "
          f"{len(rows)} held-out examples from conversations never used in training "
          f"({', '.join(sorted({r['contact'] for r in rows}))}). "
          f"Judge: {judge_llm.provider}/{judge_llm.model}.", "", *table, "",
          "## Worked examples", "",
          "_The two biggest improvements and the biggest regression._", ""]
    for r in picks:
        b, a = r["byVersion"][first], r["byVersion"][last]
        md += [f"### {r['contact']}: overall {b['overall']:.0f} → {a['overall']:.0f}", "",
               "**Client:** " + " / ".join(r["client"]), "",
               f"**Before (v{first}):** {b['reply']}", "",
               f"**After (v{last}):** {a['reply']}", "",
               f"**Real consultant:** {r['consultant']}", "",
               f"_Judge on after:_ {a['reason']}", ""]
    md += ["## Prompt changes", "", "```diff", prompt_diff(prompts[first], prompts[last]) or "(no change)", "```", "",
           "## My verdict", "", "_TODO: write whether the change improved the result and why._", ""]
    out = ROOT / "docs" / "BEFORE_AFTER.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote {out.relative_to(ROOT)} and results/eval_{ts}.json")


if __name__ == "__main__":
    main()
