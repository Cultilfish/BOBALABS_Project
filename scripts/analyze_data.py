"""Look at the sample data before writing any prompt.

Prints: dataset shape, consultant style stats, common topics, high-intent
signals, and drop-off / ghosting evidence. Results are written up in
docs/DATA_INSIGHTS.md.

Usage: python scripts/analyze_data.py [path/to/conversations.json]
"""
from __future__ import annotations

import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.conversation import build_examples, group_into_sequences, load_conversations  # noqa: E402

TOPICS = {
    "fees / pricing": r"\b(fee|fees|price|pricing|cost|thb|pay|payment)\b",
    "documents": r"\b(document|documents|statement|passport|photo|letter|invoice|contract|proof)\b",
    "bank balance 500k": r"500,?000|500k|bank balance|savings",
    "where to apply / country": r"\b(laos|malaysia|vietnam|indonesia|singapore|cambodia|taiwan|apply from)\b",
    "processing time": r"\b(how long|processing|business days|weeks?)\b",
    "interview": r"\binterview\b",
    "rejection / reapply": r"\b(reject|rejected|reapply)\b",
    "post-approval (TDAC, 90-day, entry)": r"\b(tdac|arrival card|90-day|90 day|re-?enter|border run|180 days)\b",
    "soft power (Muay Thai, cooking)": r"\b(muay thai|cooking|gym|school|soft power)\b",
}

INTENT_SIGNALS = {
    "asks how to start / next step": r"how do i (get )?start|what'?s the first step|ready to (pay|proceed)|starting now",
    "says they downloaded / signed up": r"download(ed|ing)? (the|our)? ?app|signed up|uploading|uploaded",
    "shares email / contact": r"\[email\]|my email|email is",
    "pays / sends receipt": r"transferred|paying now|payment|receipt",
    "states timeline / urgency": r"urgent|asap|expires|next week|tonight|this week",
    "already has docs ready": r"i have (all|everything)|prepared|have everything ready",
}


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.0f}%" if d else "n/a"


def main(path: str) -> None:
    convs = load_conversations(path)
    examples = build_examples(convs)

    print(f"Conversations: {len(convs)}")
    print(f"Training examples (client seq -> consultant reply): {len(examples)}")
    multi = sum(1 for e in examples if len(e.client_sequence) > 1)
    print(f"Examples where client sent 2+ messages in a row: {multi}")

    # --- consultant style ---------------------------------------------------
    replies = [e.consultant_reply for e in examples]
    words = [len(r.split()) for r in replies]
    print("\n== Consultant reply style ==")
    print(f"Words per reply: median {statistics.median(words):.0f}, "
          f"min {min(words)}, max {max(words)}")
    has_list = sum(1 for r in replies if re.search(r"^\s*(\d+\.|-)\s", r, re.M))
    has_q = sum(1 for r in replies if "?" in r)
    has_emoji = sum(1 for r in replies if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", r))
    print(f"Uses a numbered/bulleted list: {pct(has_list, len(replies))}")
    print(f"Contains a question back to the client: {pct(has_q, len(replies))}")
    print(f"Contains an emoji: {pct(has_emoji, len(replies))}")
    openers = Counter(re.split(r"[!.,]", r.strip())[0].split()[0].lower() for r in replies if r.strip())
    print(f"Most common first words: {openers.most_common(8)}")

    # --- topics ------------------------------------------------------------
    print("\n== What clients ask about (share of client sequences) ==")
    client_texts = [" ".join(e.client_sequence).lower() for e in examples]
    for name, pattern in TOPICS.items():
        n = sum(1 for t in client_texts if re.search(pattern, t))
        print(f"  {name:38s} {pct(n, len(client_texts))}")

    # --- intent ------------------------------------------------------------
    print("\n== High-intent signals (conversations containing each) ==")
    for name, pattern in INTENT_SIGNALS.items():
        hits = [c["contact_id"] for c in convs
                if any(m["direction"] == "in" and re.search(pattern, m["text"].lower())
                       for m in c["conversation"])]
        print(f"  {name:38s} {len(hits):2d}/{len(convs)}")

    # --- drop-off / ghosting -----------------------------------------------
    print("\n== Drop-off / ghosting ==")
    ends_with_client = 0
    for c in convs:
        seqs = group_into_sequences(c["conversation"])
        if seqs and seqs[-1]["role"] == "client":
            ends_with_client += 1
    print(f"Conversations ending on an unanswered client message: {ends_with_client}/{len(convs)}")
    consultant_first = sum(1 for c in convs if c["conversation"] and c["conversation"][0]["direction"] == "out")
    print(f"Conversations started by the consultant (follow-ups): {consultant_first}/{len(convs)}")
    nontext = sum(1 for c in convs for m in c["conversation"] if m["text"] == "[Non-text message]")
    print(f"Non-text messages (attachments): {nontext}")

    # --- facts the consultants repeat ---------------------------------------
    print("\n== Facts consultants repeat (count of replies mentioning) ==")
    for label, pattern in {
        "18,000 THB service fee": r"18,000",
        "Laos 5,000 + 10,000 THB": r"5,000 thb",
        "500,000 THB balance": r"500,000",
        "money-back guarantee": r"money-back",
        "app / upload": r"\bapp\b",
        "free document review": r"free",
        "ask for email": r"email",
        "working hours 10-6": r"10 am",
    }.items():
        n = sum(1 for r in replies if re.search(pattern, r.lower()))
        print(f"  {label:30s} {n}")


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent / "data" / "conversations.json"
    main(sys.argv[1] if len(sys.argv) > 1 else str(default))
