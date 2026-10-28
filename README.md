# Self-learning visa support assistant (BOBALAB take-home)

A Flask microservice that replies to Thai DTV visa clients the way the agency's human consultants do. It improves itself by comparing its replies with real consultant replies and editing its own prompt, safely and with full version history.

- **Live server:** `https://YOUR-APP.onrender.com` _(TODO)_
- **Try it:** `BASE=https://YOUR-APP.onrender.com bash docs/curl_examples.sh`
- **Results:** [docs/BEFORE_AFTER.md](docs/BEFORE_AFTER.md) · **Data findings:** [docs/DATA_INSIGHTS.md](docs/DATA_INSIGHTS.md) · **AI usage:** [AI_USAGE.md](AI_USAGE.md)

> The free Render instance sleeps when idle, so the first request can take 30-50 seconds.

---

## Quick test

```bash
curl -s -X POST https://YOUR-APP.onrender.com/generate-reply \
  -H "Content-Type: application/json" \
  -d '{"clientSequence": "I'\''m American and currently in Bali. Can I apply from Indonesia?",
       "chatHistory": [
         {"role": "client", "message": "Hello, I'\''m interested in the DTV visa. I work remotely for a US company."},
         {"role": "consultant", "message": "Hi there! May I know your nationality and which country you'\''d like to apply from?"}]}'
```

All three required endpoints, with expected responses, are in [`docs/curl_examples.sh`](docs/curl_examples.sh) and summarised under [API](#api).

---

## How it works

```
POST /generate-reply ──► load active prompt (DB) ──► LLM ──► {"aiReply"}
                                │
POST /improve-ai ───────► 1. generate predicted reply with current prompt
                          2. editor LLM compares predicted vs real consultant reply
                          3. editor returns a minimal edit + diagnosis
                          4. guardrails check the edit ──✗──► rejected, nothing saved
                          5. ✓ save as a NEW prompt version (old ones are kept)
POST /improve-ai-manually ─► same, driven by reviewer instructions (looser guardrails)
```

**Two prompts with different jobs**
- **Reply prompt** (`prompts/reply_seed.md`, then the database) holds tone, sales flow and business facts. This is the part that learns.
- **Editor prompts** (`prompts/editor_*.md`) are fixed in code. They define *how* the reply prompt may change, so the system can't rewrite its own learning rules.

**Output contract outside the editable prompt.** The "return JSON `{"reply": ...}`" instruction is appended in code (`app/assistant.py: OUTPUT_CONTRACT`). A self-edit therefore can't break parsing, which is the most common way naive self-editing prompts fail.

**Versioned, append-only storage.** Every change becomes a new row in `prompt_versions` with its source (`seed` / `auto` / `manual` / `rollback`), a change summary, the editor's diagnosis and the example that caused it. The active prompt is the highest version. Rollback appends a copy of an old version, so history is never lost.

**Guardrails on automatic edits** (`app/assistant.py: check_prompt_edit`). An edit is rejected, and not saved, if it:
- grows the prompt by more than ~25% in one step (overfitting to one example), or shrinks it by more than 30% (truncation);
- removes a section heading;
- copies a data placeholder such as `[APP_LINK]` into the prompt;
- teaches a forbidden behaviour, such as claiming to see the client's account or confirming payments;
- exceeds `MAX_PROMPT_CHARS`.

Every response includes a unified **diff** of the edit, so a reviewer can see exactly what the system learned. Add `"dryRun": true` to preview an edit without saving it.

## What I learned from the data and built in
Full write-up: [docs/DATA_INSIGHTS.md](docs/DATA_INSIGHTS.md). The main points:
- Real consultant replies have a median of 36 words, a third use lists, and they rarely use emojis. The prompt targets that register (friendly and direct) rather than slangy "casual".
- **There is no ghosting in the dataset.** Every conversation ends with the consultant, so drop-off patterns can't be learned from it. I state this rather than invent patterns, and the doc describes how I'd measure it with real data.
- **The data contains mistakes the bot shouldn't copy.** Laos fees of 5,000 + 10,000 THB are called "18,000 total" (it's 15,000). Consultants also claim account and payment access the bot doesn't have, and some coach clients on what to leave out for the embassy. The seed prompt and the editor's "never learn" list handle all three.
- The brief's example `chatHistory` is listed **newest-first**, while the data is chronological. The API defaults to oldest-first and accepts `"historyOrder": "newest_first"`.

---

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/generate-reply` | `clientSequence` (string or list), `chatHistory` (list of `{role, message}`, oldest first), optional `historyOrder` | `aiReply`, `promptVersion` |
| POST | `/improve-ai` | as above + `consultantReply`, optional `dryRun` | `predictedReply`, `updatedPrompt`, `updated`, `version`, `changeSummary`, `diagnosis`, `diff` (or `rejectedReasons`) |
| POST | `/improve-ai-manually` | `instructions`, optional `dryRun` | `updatedPrompt`, `updated`, `version`, `changeSummary`, `diff` |
| GET | `/prompt` | | active prompt version |
| GET | `/prompt/history` | | all versions, newest first (without content) |
| GET | `/prompt/<n>` | | one version with content |
| POST | `/prompt/rollback` | `version`; header `X-Admin-Token` | new version restoring version `n` |

Roles accept `client` / `consultant` (plus `user` / `assistant` as aliases). Errors return `{"error": ...}` with 400 for bad input, 401 for a missing token, 502 if the LLM fails after retries, and 503 if the DB is down.

---

## Setup

**Requirements:** Python 3.11+, an LLM API key (Gemini free tier works), and optionally a Supabase project.

```bash
git clone https://github.com/YOUR-USER/bobalab-visa-assistant && cd bobalab-visa-assistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # fill in GEMINI_API_KEY (and Supabase, see below)
pytest -q                   # 20 offline tests, no keys needed
python wsgi.py              # http://localhost:5000
```

Without `SUPABASE_URL` / `SUPABASE_KEY`, the app uses a local SQLite file, so you can run everything with only an LLM key. `LLM_PROVIDER=fake` runs fully offline.

**Supabase:** create a project, run [`schema.sql`](schema.sql) in the SQL editor, then put the project URL and the **secret key** (`sb_secret_...`, under Settings → API Keys; the legacy `service_role` key also works) in `.env`. The first request seeds version 1 from `prompts/reply_seed.md`.

**LLM providers:** `LLM_PROVIDER=gemini` (default), `anthropic`, or `openai` (any OpenAI-compatible API such as Groq). Override the model with `LLM_MODEL`. The client retries rate limits and bad JSON, and `LLM_MIN_INTERVAL_SECONDS` spaces out calls on free tiers.

**Deploy to Render:** push to GitHub, then on Render choose New → Blueprint and pick the repo. It reads [`render.yaml`](render.yaml). Set `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY` and `ADMIN_TOKEN` as environment variables. Use Supabase in production, because Render's disk is wiped on every deploy.

## Training and evaluation

```bash
python scripts/analyze_data.py                    # dataset statistics (docs/DATA_INSIGHTS.md)
python scripts/train.py --n 15                    # learn from 15 training examples
python scripts/train.py --n 15 --url $BASE        # same, through the deployed /improve-ai
python scripts/evaluate.py --versions 1 latest --n 12   # writes docs/BEFORE_AFTER.md
```

- **No leakage:** the split is by conversation. `SYNTH_011` to `SYNTH_015` are held out and never used for training (`scripts/common.py`).
- **Scoring:** an LLM judge (`prompts/judge.md`) scores each reply 1-5 against the real consultant reply on content, next step, style, human-ness and overall. Plain metrics (word count, robotic-phrase count) back it up. Set `JUDGE_PROVIDER` / `JUDGE_MODEL` to judge with a different model from the one generating replies.

## Project layout

```
app/
  __init__.py       Flask routes and error handling
  assistant.py      generate / improve logic, guardrails, diff
  conversation.py   dataset parsing and input normalisation
  llm.py            provider-agnostic LLM client (Gemini / Claude / OpenAI-compatible / fake)
  store.py          versioned prompt store (Supabase or SQLite)
prompts/            reply seed, two editor prompts, judge prompt
scripts/            analyze_data, train, evaluate
tests/              offline pytest suite
docs/               data insights, cURL examples, before/after results
schema.sql  render.yaml  wsgi.py
```

---

## Contribution summary

_TODO: rewrite this section in your own words. The reviewers want your reasoning._

**Key decisions**
- Kept the output contract out of the editable prompt, so self-learning can't break the API.
- Made storage append-only and versioned, with rollback, so a bad self-edit is recoverable and every change is auditable.
- Added guardrails and a "never learn" list, because learning from raw human replies would teach the bot real mistakes found in the data.
- Wrote the seed prompt from measured data patterns rather than a generic "helpful assistant" prompt.
- Split train and test by conversation, and built an evaluation script, so improvement claims are measured rather than eyeballed.
- Called the LLMs over plain HTTP with one small client, which makes it easy to switch provider when a free tier runs out.

**Known limitations**
- Learning is one example at a time, so edits can over-correct for one case or undo each other. Batching several examples per edit is the next step.
- The LLM judge is a model judging a model. It's useful for direction, not a precise number.
- Facts are hard-coded in the prompt from synthetic data. A real deployment needs a maintained knowledge base, with retrieval, owned by the legal team.
- The bot can't see accounts, documents or payments, and it says so instead of pretending.
- The learning endpoints are open by default so reviewers can test them. Set `PROTECT_EDIT_ENDPOINTS=true` to require the admin token.
- There's no conversation memory server-side. The caller sends the history each time, as the spec describes.

**Next steps I'd take**
- Accept an edit only if held-out scores don't drop (a validation gate), and batch examples per edit.
- Add a small web UI showing conversations, the version timeline and diffs.
- Use real conversation data to model drop-off, then flag high-intent clients for a human.

**Unfinished:** _TODO_
