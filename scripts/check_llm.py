"""Diagnose the LLM connection: which code is loaded, which Gemini models
your key can use, and how long a tiny request takes.

Usage: python scripts/check_llm.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.llm import LLMClient  # noqa: E402

c = LLMClient()
print(f"provider={c.provider} model={c.model} timeout={c.timeout}s "
      f"retries={getattr(c, 'retries', 'OLD CODE (no retries setting)')} "
      f"thinking={os.getenv('GEMINI_THINKING_LEVEL') or '(default)'}")

if c.provider == "gemini":
    key = os.environ["GEMINI_API_KEY"]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    print("\nModels your key can call (flash / lite ones are fastest):")
    for n in sorted(names):
        if "flash" in n or "lite" in n:
            print("  ", n)

print("\nTiming a tiny request...")
t0 = time.monotonic()
try:
    out = c.complete_json("Return JSON {\"reply\": \"pong\"}", "ping", max_tokens=256, retries=1)
    print(f"OK in {time.monotonic() - t0:.1f}s -> {out}")
except Exception as e:
    print(f"FAILED after {time.monotonic() - t0:.1f}s: {e}")