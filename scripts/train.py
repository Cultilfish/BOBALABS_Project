"""Run the self-learning loop over training examples.

Each example: generate a reply with the current prompt, compare with the
real consultant reply, let the editor propose a minimal edit, run the
guardrails, and save a new prompt version if accepted.

Usage:
  python scripts/train.py --n 15            # in-process, writes to your DB
  python scripts/train.py --n 15 --url https://your-app.onrender.com
                                            # through the deployed /improve-ai endpoint
  python scripts/train.py --n 5 --dry-run   # show proposed edits, save nothing
"""
from __future__ import annotations

import argparse
import json
import time

import requests

from common import ROOT, load_split, make_assistant, spread


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15, help="number of training examples to learn from")
    ap.add_argument("--url", help="base URL of a deployed server (otherwise runs in-process)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    train, _ = load_split()
    examples = spread(train, args.n)
    print(f"Training on {len(examples)} of {len(train)} training examples\n")
    assistant = None if args.url else make_assistant()

    log = []
    for i, ex in enumerate(examples, 1):
        payload = {**ex.to_api_payload(), "dryRun": args.dry_run}
        t0 = time.monotonic()
        try:
            if args.url:
                r = requests.post(args.url.rstrip("/") + "/improve-ai", json=payload, timeout=180)
                r.raise_for_status()
                res = r.json()
            else:
                res = assistant.improve_from_example(ex.client_sequence, ex.chat_history,
                                                     ex.consultant_reply, dry_run=args.dry_run)
        except Exception as e:  # keep going; one bad call shouldn't stop the run
            print(f"[{i}/{len(examples)}] {ex.contact_id} ERROR: {e}")
            log.append({"contact": ex.contact_id, "error": str(e)})
            continue

        status = "UPDATED" if res.get("updated") else ("REJECTED" if res.get("rejectedReasons") else "no change")
        print(f"[{i}/{len(examples)}] {ex.contact_id} v{res.get('previousVersion')}->v{res.get('version')} "
              f"{status} ({time.monotonic() - t0:.0f}s)")
        print(f"    client:  {' / '.join(ex.client_sequence)[:100]}")
        print(f"    change:  {res.get('changeSummary')}")
        if res.get("rejectedReasons"):
            print(f"    blocked: {res['rejectedReasons']}")
        log.append({"contact": ex.contact_id, "clientSequence": ex.client_sequence,
                    "consultantReply": ex.consultant_reply, **{k: v for k, v in res.items() if k != "updatedPrompt"}})

    out = ROOT / "results" / f"train_log_{int(time.time())}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    updated = sum(1 for e in log if e.get("updated"))
    rejected = sum(1 for e in log if e.get("rejectedReasons"))
    print(f"\nDone: {updated} updates, {rejected} rejected by guardrails, "
          f"{len(log) - updated - rejected} unchanged/errors. Log: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
