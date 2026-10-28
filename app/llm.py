"""Tiny provider-agnostic LLM client that always returns parsed JSON.

Providers (LLM_PROVIDER):
  gemini     - Google AI Studio key in GEMINI_API_KEY (default)
  anthropic  - Claude, key in ANTHROPIC_API_KEY
  openai     - any OpenAI-compatible API (OpenAI, Groq, ...) via
               OPENAI_API_KEY and OPENAI_BASE_URL
  fake       - deterministic offline stub for tests

Plain HTTP via `requests` instead of three SDKs: fewer dependencies, and
the request/response shape is visible in one file.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

import requests

DEFAULT_MODELS = {
    "gemini": "gemini-3.5-flash",
    "anthropic": "claude-haiku-4-5",
    "openai": "llama-3.3-70b-versatile",  # Groq default; set LLM_MODEL for OpenAI
}


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    """Parse a JSON object out of model output, tolerating ```json fences
    or chatter around it."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"Model did not return JSON: {text[:200]!r}")
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise LLMError(f"Model returned invalid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise LLMError("Model returned JSON that is not an object")
    return obj


class LLMClient:
    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
        if self.provider not in DEFAULT_MODELS and self.provider != "fake":
            raise LLMError(f"Unknown LLM_PROVIDER {self.provider!r}")
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(self.provider, "fake")
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
        self.retries = int(os.getenv("LLM_RETRIES", "2"))
        self._thinking_unsupported = False
        # Free tiers have low requests-per-minute limits; space calls out.
        self.min_interval = float(os.getenv("LLM_MIN_INTERVAL_SECONDS", "0"))
        self._last_call = 0.0
        self._lock = threading.Lock()

    # -- public ---------------------------------------------------------
    def complete_json(self, system: str, user: str, temperature: float = 0.4,
                      max_tokens: int = 4096, retries: int | None = None) -> dict:
        retries = retries or self.retries
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                self._throttle()
                raw = self._call(system, user, temperature, max_tokens)
                return extract_json(raw)
            except LLMError as e:  # bad JSON or retryable HTTP error
                last_err = e
                if attempt < retries - 1:
                    time.sleep(min(2 ** attempt * 2, 10))
        raise LLMError(f"LLM call failed after {retries} attempts: {last_err}")

    # -- internals ------------------------------------------------------
    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMError(f"Network error: {e}") from e
        if r.status_code == 429 or r.status_code >= 500:
            raise LLMError(f"Retryable HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            # Not retryable (bad key, bad model name...): fail fast with a clear message.
            raise LLMFatalError(f"HTTP {r.status_code} from {self.provider}: {r.text[:300]}")
        return r.json()

    def _call(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        if self.provider == "fake":
            return fake_response(system, user)
        if self.provider == "gemini":
            key = _require_env("GEMINI_API_KEY")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            gen_config = {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            }
            # Thinking models can be slow. GEMINI_THINKING_LEVEL (e.g. "low",
            # "minimal") trades depth for speed; unset = model default.
            level = os.getenv("GEMINI_THINKING_LEVEL", "").strip()
            if level and not self._thinking_unsupported:
                gen_config["thinkingConfig"] = {"thinkingLevel": level}
            payload = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": gen_config,
            }
            try:
                data = self._post(url, {"x-goog-api-key": key}, payload)
            except LLMFatalError as e:
                if "thinking" in str(e).lower() and "thinkingConfig" in gen_config:
                    # Model doesn't accept this thinking setting: drop it and carry on.
                    self._thinking_unsupported = True
                    gen_config.pop("thinkingConfig")
                    data = self._post(url, {"x-goog-api-key": key}, payload)
                else:
                    raise
            try:
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts if not p.get("thought"))
            except (KeyError, IndexError) as e:
                reason = (data.get("candidates") or [{}])[0].get("finishReason")
                raise LLMError(f"Unexpected Gemini response (finishReason={reason}): {str(data)[:300]}") from e
        if self.provider == "anthropic":
            key = _require_env("ANTHROPIC_API_KEY")
            data = self._post("https://api.anthropic.com/v1/messages", {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            }, {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            })
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        # openai-compatible
        key = _require_env("OPENAI_API_KEY")
        base = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        data = self._post(f"{base}/chat/completions", {"Authorization": f"Bearer {key}"}, {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        })
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected response: {str(data)[:300]}") from e


class LLMFatalError(Exception):
    """Configuration problems (bad key, unknown model). Not retried."""


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise LLMFatalError(f"{name} is not set")
    return v


def fake_response(system: str, user: str) -> str:
    """Offline stub so tests and local demos run without an API key."""
    if '"prompt"' in system:  # editor call
        current = user.split("CURRENT PROMPT:\n", 1)[-1].split("\n\n=== ", 1)[0]
        return json.dumps({
            "diagnosis": "fake diagnosis",
            "changeSummary": "fake edit: added a test rule",
            "prompt": current.rstrip() + "\n- (fake) Test rule added by the editor.",
        })
    if '"score' in system or "judge" in system.lower():
        return json.dumps({"content": 3, "style": 3, "nextStep": 3, "human": 3, "overall": 3, "reason": "fake"})
    return json.dumps({"reply": "Hi! Yes, that works. May I know your nationality and where you'd like to apply from?"})