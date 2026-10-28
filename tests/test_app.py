"""Offline tests: fake LLM + temporary SQLite store. Run: pytest -q"""
import json
from pathlib import Path

import pytest

from app import create_app
from app.assistant import check_prompt_edit
from app.conversation import build_examples, group_into_sequences, load_conversations, normalise_history
from app.llm import LLMClient, extract_json
from app.store import SQLiteStore

DATA = Path(__file__).resolve().parent.parent / "data" / "conversations.json"
SEED = (Path(__file__).resolve().parent.parent / "prompts" / "reply_seed.md").read_text()

HISTORY = [
    {"role": "client", "message": "Hello, I'm interested in the DTV visa for Thailand. I work remotely."},
    {"role": "consultant", "message": "Hi there! May I know your nationality and where you'd like to apply from?"},
]


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(str(tmp_path / "t.db"))


@pytest.fixture
def client(store):
    app = create_app(store=store, llm=LLMClient(provider="fake"))
    return app.test_client()


# --- data parsing ----------------------------------------------------------
def test_examples_cover_every_client_sequence():
    convs = load_conversations(DATA)
    examples = build_examples(convs)
    expected = 0
    for c in convs:
        seqs = group_into_sequences(c["conversation"])
        expected += sum(1 for i, s in enumerate(seqs[:-1]) if s["role"] == "client" and seqs[i + 1]["role"] == "consultant")
    assert len(examples) == expected > 100


def test_history_precedes_sequence_and_is_chronological():
    ex = build_examples(load_conversations(DATA))
    first = ex[1]  # second turn of SYNTH_001
    assert first.chat_history[0]["role"] == "client"
    assert first.chat_history[-1]["role"] == "consultant"
    assert first.client_sequence == ["I'm American and currently in Bali. Can I apply from Indonesia?"]


def test_consecutive_client_messages_are_grouped():
    ex = build_examples(load_conversations(DATA))
    assert any(len(e.client_sequence) > 1 for e in ex)


def test_consultant_first_conversation_handled():
    ex = [e for e in build_examples(load_conversations(DATA)) if e.contact_id == "SYNTH_012"]
    assert ex[0].chat_history[0]["role"] == "consultant"


def test_newest_first_history_is_reversed():
    h = normalise_history(list(reversed(HISTORY)), "newest_first")
    assert h[0]["role"] == "client"


# --- LLM JSON parsing ------------------------------------------------------
@pytest.mark.parametrize("raw", ['{"reply": "hi"}', '```json\n{"reply": "hi"}\n```', 'Sure! {"reply": "hi"} done'])
def test_extract_json_tolerates_wrappers(raw):
    assert extract_json(raw) == {"reply": "hi"}


# --- endpoints -------------------------------------------------------------
def test_generate_reply(client):
    r = client.post("/generate-reply", json={"clientSequence": "Can I apply from Indonesia?", "chatHistory": HISTORY})
    assert r.status_code == 200
    data = r.get_json()
    assert data["aiReply"] and data["promptVersion"] == 1


def test_generate_reply_accepts_list_and_no_history(client):
    r = client.post("/generate-reply", json={"clientSequence": ["Hi", "Is DTV good for Muay Thai?"]})
    assert r.status_code == 200


@pytest.mark.parametrize("payload", [{}, {"clientSequence": ""}, {"clientSequence": "hi", "chatHistory": [{"role": "x", "message": "y"}]}])
def test_generate_reply_validates_input(client, payload):
    assert client.post("/generate-reply", json=payload).status_code == 400


def test_improve_ai_saves_new_version(client, store):
    r = client.post("/improve-ai", json={
        "clientSequence": "Can I apply from Indonesia?", "chatHistory": HISTORY,
        "consultantReply": "Yes, you can apply from Indonesia! Fee is 18,000 THB."})
    data = r.get_json()
    assert r.status_code == 200, data
    assert data["updated"] is True and data["version"] == 2
    assert data["predictedReply"] and "updatedPrompt" in data and data["diff"].startswith("---")
    assert store.get_active().version == 2


def test_improve_ai_dry_run_does_not_save(client, store):
    client.post("/improve-ai", json={"clientSequence": "x?", "chatHistory": [], "consultantReply": "y", "dryRun": True})
    assert store.get_active().version == 1


def test_improve_manually_and_rollback(client, store):
    r = client.post("/improve-ai-manually", json={"instructions": "Be more concise."})
    assert r.get_json()["version"] == 2
    r = client.post("/prompt/rollback", json={"version": 1})
    assert r.status_code == 200 and r.get_json()["version"] == 3
    assert store.get_active().content == store.get("reply", 1).content
    hist = client.get("/prompt/history").get_json()["versions"]
    assert [v["source"] for v in hist] == ["rollback", "manual", "seed"]


def test_rollback_requires_token_when_set(store, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    c = create_app(store=store, llm=LLMClient(provider="fake")).test_client()
    store.get_active()
    assert c.post("/prompt/rollback", json={"version": 1}).status_code == 401
    assert c.post("/prompt/rollback", json={"version": 1}, headers={"X-Admin-Token": "secret"}).status_code == 200


# --- guardrails ------------------------------------------------------------
def test_guardrail_accepts_small_edit():
    assert check_prompt_edit(SEED, SEED + "\n- Keep replies under 50 words.\n").ok


def test_guardrail_rejects_truncation_growth_and_bad_lessons():
    assert not check_prompt_edit(SEED, SEED[: len(SEED) // 2]).ok
    assert not check_prompt_edit(SEED, SEED + "x" * 5000).ok
    assert not check_prompt_edit(SEED, SEED + "\n- Send the link [APP_LINK].\n").ok
    assert not check_prompt_edit(SEED, SEED + "\n- Say: I found your account.\n").ok
    assert not check_prompt_edit(SEED, SEED.replace("## How you sound", "## Tone")).ok


def test_guardrail_rejection_does_not_save(store, monkeypatch):
    llm = LLMClient(provider="fake")
    monkeypatch.setattr("app.llm.fake_response", lambda s, u: json.dumps(
        {"prompt": "too short", "changeSummary": "bad"}) if '"prompt"' in s else json.dumps({"reply": "hi"}))
    c = create_app(store=store, llm=llm).test_client()
    data = c.post("/improve-ai", json={"clientSequence": "x?", "consultantReply": "y"}).get_json()
    assert data["updated"] is False and data["rejectedReasons"]
    assert store.get_active().version == 1
