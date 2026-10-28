"""Versioned prompt storage.

Every change is appended as a new version; nothing is overwritten. The
active prompt is simply the highest version. Rolling back = appending a
copy of an older version, so history stays complete and auditable.

Backends:
  SupabaseStore - production (Supabase Postgres through its REST API)
  SQLiteStore   - local development and tests (no account needed)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

REPLY_PROMPT = "reply"
SEED_PATH = Path(__file__).resolve().parent.parent / "prompts" / "reply_seed.md"


@dataclass
class PromptVersion:
    prompt_name: str
    version: int
    content: str
    source: str  # seed | auto | manual | rollback
    change_summary: str = ""
    metadata: dict | None = None
    created_at: str = ""

    def to_dict(self, include_content: bool = True) -> dict:
        d = asdict(self)
        if not include_content:
            d.pop("content")
            d["length"] = len(self.content)
        return d


class StoreError(RuntimeError):
    pass


class PromptStore:
    """Interface + shared behaviour."""

    def latest(self, name: str) -> PromptVersion | None:
        raise NotImplementedError

    def get(self, name: str, version: int) -> PromptVersion | None:
        raise NotImplementedError

    def history(self, name: str, limit: int = 50) -> list[PromptVersion]:
        raise NotImplementedError

    def _insert(self, pv: PromptVersion) -> PromptVersion:
        raise NotImplementedError

    # -- shared -----------------------------------------------------------
    def get_active(self, name: str = REPLY_PROMPT) -> PromptVersion:
        pv = self.latest(name)
        if pv is None:
            # First run: seed from the file in the repo.
            pv = self.save(name, SEED_PATH.read_text(encoding="utf-8"), "seed", "initial seed prompt")
        return pv

    def save(self, name: str, content: str, source: str, change_summary: str = "",
             metadata: dict | None = None) -> PromptVersion:
        for _ in range(3):  # retry if two writers race for the same version number
            current = self.latest(name)
            pv = PromptVersion(
                prompt_name=name,
                version=(current.version + 1) if current else 1,
                content=content,
                source=source,
                change_summary=change_summary,
                metadata=metadata or {},
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            try:
                return self._insert(pv)
            except _VersionConflict:
                continue
        raise StoreError("Could not save prompt version (concurrent writes)")

    def rollback(self, name: str, to_version: int) -> PromptVersion:
        old = self.get(name, to_version)
        if old is None:
            raise StoreError(f"Version {to_version} of '{name}' not found")
        return self.save(name, old.content, "rollback", f"rolled back to v{to_version}",
                         {"rolledBackTo": to_version})


class _VersionConflict(Exception):
    pass


# ---------------------------------------------------------------------------
class SQLiteStore(PromptStore):
    def __init__(self, path: str = "prompts.db"):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS prompt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_name TEXT NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                change_summary TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(prompt_name, version)
            )"""
        )
        self._conn.commit()

    def _row(self, r) -> PromptVersion:
        return PromptVersion(r[0], r[1], r[2], r[3], r[4] or "", json.loads(r[5] or "{}"), r[6])

    _COLS = "prompt_name, version, content, source, change_summary, metadata, created_at"

    def latest(self, name):
        with self._lock:
            r = self._conn.execute(
                f"SELECT {self._COLS} FROM prompt_versions WHERE prompt_name=? ORDER BY version DESC LIMIT 1",
                (name,)).fetchone()
        return self._row(r) if r else None

    def get(self, name, version):
        with self._lock:
            r = self._conn.execute(
                f"SELECT {self._COLS} FROM prompt_versions WHERE prompt_name=? AND version=?",
                (name, version)).fetchone()
        return self._row(r) if r else None

    def history(self, name, limit=50):
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {self._COLS} FROM prompt_versions WHERE prompt_name=? ORDER BY version DESC LIMIT ?",
                (name, limit)).fetchall()
        return [self._row(r) for r in rows]

    def _insert(self, pv):
        try:
            with self._lock:
                self._conn.execute(
                    f"INSERT INTO prompt_versions ({self._COLS}) VALUES (?,?,?,?,?,?,?)",
                    (pv.prompt_name, pv.version, pv.content, pv.source, pv.change_summary,
                     json.dumps(pv.metadata or {}), pv.created_at))
                self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise _VersionConflict() from e
        return pv


# ---------------------------------------------------------------------------
class SupabaseStore(PromptStore):
    """Talks to Supabase's auto-generated REST API (PostgREST).
    Table definition: schema.sql."""

    TABLE = "prompt_versions"

    def __init__(self, url: str, key: str):
        self.base = f"{url.rstrip('/')}/rest/v1/{self.TABLE}"
        # New-style keys (sb_secret_...) go in the apikey header only.
        # Legacy service_role keys are JWTs ("eyJ...") and also need Authorization.
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):
            self.headers["Authorization"] = f"Bearer {key}"

    def _get(self, params: dict) -> list[dict]:
        try:
            r = requests.get(self.base, headers=self.headers, params=params, timeout=15)
        except requests.RequestException as e:
            raise StoreError(f"Supabase unreachable: {e}") from e
        if r.status_code >= 400:
            raise StoreError(f"Supabase error {r.status_code}: {r.text[:300]}")
        return r.json()

    @staticmethod
    def _row(d: dict) -> PromptVersion:
        return PromptVersion(d["prompt_name"], d["version"], d["content"], d["source"],
                             d.get("change_summary") or "", d.get("metadata") or {},
                             d.get("created_at") or "")

    def latest(self, name):
        rows = self._get({"prompt_name": f"eq.{name}", "order": "version.desc", "limit": 1})
        return self._row(rows[0]) if rows else None

    def get(self, name, version):
        rows = self._get({"prompt_name": f"eq.{name}", "version": f"eq.{version}"})
        return self._row(rows[0]) if rows else None

    def history(self, name, limit=50):
        rows = self._get({"prompt_name": f"eq.{name}", "order": "version.desc", "limit": limit})
        return [self._row(r) for r in rows]

    def _insert(self, pv):
        body = pv.to_dict()
        try:
            r = requests.post(self.base, headers={**self.headers, "Prefer": "return=representation"},
                              json=body, timeout=15)
        except requests.RequestException as e:
            raise StoreError(f"Supabase unreachable: {e}") from e
        if r.status_code == 409:
            raise _VersionConflict()
        if r.status_code >= 400:
            raise StoreError(f"Supabase insert failed {r.status_code}: {r.text[:300]}")
        return self._row(r.json()[0])


def store_from_env() -> PromptStore:
    # strip(): a stray space pasted into a hosting dashboard broke the URL once.
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_KEY") or "").strip()
    if url and key:
        return SupabaseStore(url, key)
    return SQLiteStore(os.getenv("SQLITE_PATH", "prompts.db"))
