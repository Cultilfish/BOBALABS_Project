"""Flask app factory: HTTP layer only. Logic lives in assistant.py."""
from __future__ import annotations

import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from .assistant import Assistant
from .conversation import InputError, normalise_client_sequence, normalise_history
from .llm import LLMClient, LLMError, LLMFatalError
from .store import REPLY_PROMPT, PromptStore, StoreError, store_from_env

log = logging.getLogger("visa-assistant")


def create_app(store: PromptStore | None = None, llm: LLMClient | None = None) -> Flask:
    load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.json.sort_keys = False
    store = store or store_from_env()
    llm = llm or LLMClient()
    assistant = Assistant(store, llm)
    admin_token = os.getenv("ADMIN_TOKEN")
    protect_edits = os.getenv("PROTECT_EDIT_ENDPOINTS", "false").lower() == "true"

    def body() -> dict:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise InputError("Request body must be a JSON object")
        return data

    def require_admin():
        if admin_token and request.headers.get("X-Admin-Token") != admin_token:
            raise PermissionError("Missing or wrong X-Admin-Token header")

    def parse_conversation(data: dict):
        seq = normalise_client_sequence(data.get("clientSequence"))
        hist = normalise_history(data.get("chatHistory"), data.get("historyOrder", "oldest_first"))
        return seq, hist

    # ------------------------------------------------------------- errors
    @app.errorhandler(InputError)
    def _bad_input(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(PermissionError)
    def _forbidden(e):
        return jsonify(error=str(e)), 401

    @app.errorhandler(LLMError)
    def _llm(e):
        log.warning("LLM error: %s", e)
        return jsonify(error="The language model failed to respond. Please retry.", detail=str(e)), 502

    @app.errorhandler(LLMFatalError)
    def _llm_fatal(e):
        log.error("LLM configuration error: %s", e)
        return jsonify(error="Server LLM configuration error", detail=str(e)), 500

    @app.errorhandler(StoreError)
    def _store(e):
        log.error("Store error: %s", e)
        return jsonify(error="Prompt database unavailable", detail=str(e)), 503

    @app.errorhandler(ValueError)
    def _value(e):
        return jsonify(error=str(e)), 502

    # ------------------------------------------------------------- routes
    @app.get("/")
    def index():
        return jsonify(
            service="BOBALAB self-learning visa support assistant",
            endpoints={
                "POST /generate-reply": "reply to client message(s) given chat history",
                "POST /improve-ai": "learn from a real consultant reply",
                "POST /improve-ai-manually": "apply reviewer instructions to the prompt",
                "GET /prompt": "current active prompt",
                "GET /prompt/history": "all prompt versions (newest first)",
                "GET /prompt/<version>": "one prompt version",
                "POST /prompt/rollback": "restore an older version (admin token)",
            },
            llm={"provider": llm.provider, "model": llm.model},
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/generate-reply")
    def generate_reply():
        seq, hist = parse_conversation(body())
        t0 = time.monotonic()
        reply, version = assistant.generate_reply(seq, hist)
        log.info("generate-reply v%s in %.1fs", version, time.monotonic() - t0)
        return jsonify(aiReply=reply, promptVersion=version)

    @app.post("/improve-ai")
    def improve_ai():
        if protect_edits:
            require_admin()
        data = body()
        seq, hist = parse_conversation(data)
        consultant = data.get("consultantReply")
        if not isinstance(consultant, str) or not consultant.strip():
            raise InputError("consultantReply must be a non-empty string")
        result = assistant.improve_from_example(seq, hist, consultant.strip(),
                                                dry_run=bool(data.get("dryRun")))
        log.info("improve-ai: updated=%s v%s %s", result["updated"], result["version"],
                 result.get("changeSummary"))
        return jsonify(result)

    @app.post("/improve-ai-manually")
    def improve_ai_manually():
        if protect_edits:
            require_admin()
        data = body()
        instructions = data.get("instructions")
        if not isinstance(instructions, str) or not instructions.strip():
            raise InputError("instructions must be a non-empty string")
        result = assistant.improve_manually(instructions.strip(), dry_run=bool(data.get("dryRun")))
        log.info("improve-ai-manually: updated=%s v%s", result["updated"], result["version"])
        return jsonify(result)

    @app.get("/prompt")
    def get_prompt():
        return jsonify(store.get_active(REPLY_PROMPT).to_dict())

    @app.get("/prompt/history")
    def prompt_history():
        limit = min(int(request.args.get("limit", 50)), 200)
        store.get_active(REPLY_PROMPT)  # make sure a seed exists
        return jsonify(versions=[v.to_dict(include_content=False) for v in store.history(REPLY_PROMPT, limit)])

    @app.get("/prompt/<int:version>")
    def prompt_version(version: int):
        pv = store.get(REPLY_PROMPT, version)
        if pv is None:
            return jsonify(error=f"version {version} not found"), 404
        return jsonify(pv.to_dict())

    @app.post("/prompt/rollback")
    def rollback():
        require_admin()
        data = body()
        version = data.get("version")
        if not isinstance(version, int):
            raise InputError("version must be an integer")
        if store.get(REPLY_PROMPT, version) is None:
            return jsonify(error=f"version {version} not found"), 404
        pv = store.rollback(REPLY_PROMPT, version)
        return jsonify(pv.to_dict(include_content=False))

    return app
