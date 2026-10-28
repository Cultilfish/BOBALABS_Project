"""Rule-based question categories for client messages.

Deterministic keyword rules (no API calls) so the same message always gets
the same label. Used for:
  - the question-type distribution report (scripts/question_distribution.py)
  - category-balanced training (scripts/train.py --balanced)

The first matching rule wins, so more specific categories come first.
"""
from __future__ import annotations

import re
from collections import defaultdict

# (name, description, pattern). Order matters.
QUESTION_CATEGORIES: list[tuple[str, str, str]] = [
    ("Rejection & reapplication", "Visa was refused; can they reapply and where",
     r"reject|reapply|insufficient documentation"),
    ("Embassy interview", "Preparing for an in-person embassy interview",
     r"interview|what questions|not say|what time should i arrive|should i mention"),
    ("After approval & staying", "TDAC, re-entry, 180-day stays, border runs, 90-day reporting, work rules",
     r"approved!|arrival card|printout|re-?enter|each entry|90-day|extend|border run|"
     r"work for thai|in trouble for being late|report again"),
    ("Payment", "Paying, payment problems, bank transfer",
     r"\bpay\b|payment|transfer|card|receipt|paying"),
    ("Fees & guarantee", "Service fees, government fees, money-back guarantee",
     r"\bfees?\b|pricing|price|cost|cheaper|how much is|money-back|guarantee|hidden|free\?"),
    ("Bank balance & finances", "500,000 THB rule, crypto, stocks, currency",
     r"bank|crypto|stocks?|savings|500k|500,000|balance|convert|sgd|usd|\$"),
    ("Documents", "Which documents, translations, address proof, photos, formats",
     r"document|translation|invoice|address|license|photo|records|format|acceptable|"
     r"missing|6 months okay|need from me|enrollment letter|what do they need|online system"),
    ("Timeline & processing", "Processing times, how long to stay, urgency",
     r"how long|processing|how quickly|budget|accommodation|fastest|hear back|urgent|expires"),
    ("DTV rules & eligibility", "What the visa allows: Thai clients, beginners, exceptions to rules",
     r"thai (company|client)|way around|is that a problem"),
    ("Where & how to apply", "Eligibility, which country/embassy, visa type, switching from tourist visa",
     r"apply|country|embassy|switch|gym|enroll|beginner|muay thai|cooking|freelance|"
     r"get started|first step|start the process|whatsapp|anything else|upload\?"),
]

# Messages without a question are statements, not questions.
STATEMENT_CATEGORIES: list[tuple[str, str, str]] = [
    # A statement can still clearly be about a topic.
    ("Rejection & reapplication", "", r"reject|insufficient documentation"),
    ("After approval & staying", "", r"dtv is approved"),
    ("Payment", "", r"issues with the payment|keeps failing"),
    ("Progress update (high intent)", "Signed up, uploading, paying, travelling: ready to proceed",
     r"download|signed up|upload|paying|transferred|starting now|on it|i'll do that|"
     r"get the translations|get everything together|flying|\[email\]|sent everything|"
     r"have everything ready|start uploading|will wait"),
    ("Thanks & closing", "Thank-yous, sign-offs, encouragement",
     r"thank|thanks|wish me luck|will do|great 👍|worth it|exciting"),
    ("Sharing situation", "Introduces themselves or answers the consultant's questions",
     r"."),
]

OTHER = "Other"


def all_categories() -> list[tuple[str, str]]:
    seen, out = set(), []
    for n, d, _ in QUESTION_CATEGORIES + STATEMENT_CATEGORIES:
        if n not in seen:
            seen.add(n)
            out.append((n, d))
    return out + [(OTHER, "No rule matched")]


def categorize(messages: list[str]) -> str:
    text = " ".join(messages).lower()
    rules = QUESTION_CATEGORIES if "?" in text else STATEMENT_CATEGORIES
    for name, _, pattern in rules:
        if re.search(pattern, text):
            return name
    return OTHER


def balanced_sample(examples: list, n: int) -> list:
    """Category-balanced selection, the prompt-learning version of
    oversampling rare classes: take examples round-robin across categories,
    rarest category first, so rare situations (interviews, rejections)
    are represented instead of being drowned out by common ones.

    Each example is used at most once. Exact duplicates teach a prompt editor
    nothing new; they only repeat the same edit.
    """
    groups: dict[str, list] = defaultdict(list)
    for ex in examples:
        groups[categorize(ex.client_sequence)].append(ex)
    order = sorted(groups, key=lambda c: (len(groups[c]), c))
    picked: list = []
    idx = {c: 0 for c in order}
    while len(picked) < n and any(idx[c] < len(groups[c]) for c in order):
        for c in order:
            if len(picked) >= n:
                break
            if idx[c] < len(groups[c]):
                # Spread picks within a category across conversations.
                g = groups[c]
                step = max(1, len(g) // max(1, n // len(order) + 1))
                j = (idx[c] * step) % len(g)
                while g[j] in picked:
                    j = (j + 1) % len(g)
                picked.append(g[j])
                idx[c] += 1
    return picked
