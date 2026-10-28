"""Shared setup for scripts: data split and object construction."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from app.assistant import Assistant  # noqa: E402
from app.conversation import Example, build_examples, load_conversations, split_by_contact  # noqa: E402
from app.llm import LLMClient  # noqa: E402
from app.store import store_from_env  # noqa: E402

load_dotenv(ROOT / ".env")

DATA = ROOT / "data" / "conversations.json"
# Held-out conversations: never used for training, only for evaluation.
# Chosen to cover different scenario types (switching visas, follow-up,
# extensions, pricing, urgent case).
TEST_IDS = {"SYNTH_011", "SYNTH_012", "SYNTH_013", "SYNTH_014", "SYNTH_015"}


def load_split() -> tuple[list[Example], list[Example]]:
    return split_by_contact(build_examples(load_conversations(DATA)), TEST_IDS)


def spread(items: list, n: int) -> list:
    """Pick n items evenly spread across the list (deterministic)."""
    if n >= len(items):
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def make_assistant() -> Assistant:
    return Assistant(store_from_env(), LLMClient())
