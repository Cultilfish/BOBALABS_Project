# 1. Setup and usage: running the code and talking to the assistant

This document covers how to try the live service, how to run it yourself, how to talk to the assistant, and how another lab member would maintain it.

- **Live server:** https://bobalab-visa-assistant.onrender.com
- **Free hosting:** the first request after a quiet period can take about 50 seconds while the server wakes up.

---

## 1.1 Try the live service in 1 minute

Open these in a browser:
- https://bobalab-visa-assistant.onrender.com/ shows the service, its endpoints and the model it's running.
- https://bobalab-visa-assistant.onrender.com/prompt/history shows every version of the assistant's prompt and how it changed.

Then send it a message with cURL:

```bash
curl -s -X POST https://bobalab-visa-assistant.onrender.com/generate-reply \
  -H "Content-Type: application/json" \
  -d '{"clientSequence": "I'\''m American and currently in Bali. Can I apply from Indonesia?",
       "chatHistory": [
         {"role": "client", "message": "Hello, I'\''m interested in the DTV visa. I work remotely for a US company."},
         {"role": "consultant", "message": "Hi there! May I know your nationality and which country you'\''d like to apply from?"}]}'
```

**Windows:** run the full end-to-end check, 8 tests across all endpoints:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_live.ps1
```

**macOS / Linux:** run all the cURL examples:
```bash
BASE=https://bobalab-visa-assistant.onrender.com bash docs/curl_examples.sh
```

---

## 1.2 The three endpoints: requests and expected responses

### `POST /generate-reply`: get the assistant's reply
**Request**
```json
{
  "clientSequence": "I'm American and currently in Bali. Can I apply from Indonesia?",
  "chatHistory": [
    { "role": "client", "message": "Hello, I'm interested in the DTV visa for Thailand. I work remotely as a software developer for a US company." },
    { "role": "consultant", "message": "Hi there! May I know your nationality and which country you'd like to apply from?" }
  ]
}
```
- `clientSequence` is one message (a string) or several in a row (a list of strings).
- `chatHistory` is **oldest first** by default. Add `"historyOrder": "newest_first"` if you list it the other way, as the brief's own example does.
- Roles are `client` / `consultant` (`user` / `assistant` also accepted).

**Response** (real output from the live server)
```json
{
  "aiReply": "Yes, you can apply from Indonesia! Since you're an American working remotely, you'll just need your US passport, 3 months of bank statements showing at least 500k THB, your remote work contract or employer letter, recent payslips, and proof of your stay in Bali.\n\nTo start, download our app, create an account, and upload your documents for a free review by our legal team. What email will you use to sign up?",
  "promptVersion": 1
}
```

### `POST /improve-ai`: learn from a real consultant reply
**Request**
```bash
curl -s -X POST https://bobalab-visa-assistant.onrender.com/improve-ai \
  -H "Content-Type: application/json" \
  -d '{"clientSequence": "I'\''m American and currently in Bali. Can I apply from Indonesia?",
       "chatHistory": [],
       "consultantReply": "Yes, you can apply from Indonesia! For remote workers, our service fees are 18,000 THB including all government fees. The processing time in Indonesia is typically around 10 business days.",
       "dryRun": true}'
```
`"dryRun": true` shows the proposed edit **without saving it**. Leave it out to save the new version.

**Response** (shape of the response; the wording varies from run to run)
```json
{
  "predictedReply": "Yes, you can apply from Indonesia! ...",
  "diagnosis": "The consultant gave price and processing time; the bot skipped to the app.",
  "changeSummary": "Mention fee and processing time when a client confirms their application country.",
  "previousVersion": 9,
  "updated": false,
  "dryRun": true,
  "updatedPrompt": "You are a member of the customer support team ... (the proposed new prompt)",
  "version": 9,
  "diff": "--- current\n+++ proposed\n@@ ... @@\n- ...\n+ ..."
}
```
Without `dryRun`, the edit is saved: `"updated": true` and `"version": 10`.
If the guardrails block the edit, `updated` is `false` and `rejectedReasons` lists why. If the editor finds nothing worth changing, `changeSummary` is `"no change"`.

### `POST /improve-ai-manually`: apply a reviewer's instructions
```bash
curl -s -X POST https://bobalab-visa-assistant.onrender.com/improve-ai-manually \
  -H "Content-Type: application/json" \
  -d '{"instructions": "Be more concise. Always mention appointment booking proactively.", "dryRun": true}'
```
**Response** (shape of the response)
```json
{ "changeSummary": "...", "previousVersion": 9, "updated": false, "dryRun": true, "updatedPrompt": "...", "version": 9, "diff": "..." }
```

### Extra endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/prompt` | Current active prompt |
| GET | `/prompt/history` | All versions, newest first: source, change summary, size |
| GET | `/prompt/<n>` | One version with its full text |
| POST | `/prompt/rollback` | `{"version": n}` with header `X-Admin-Token`: restore an older version (saved as a new version, so nothing is lost) |
| GET | `/health` | Health check for the host |

**Errors:** `400` for bad input (with a message), `401` for a missing admin token, `502` if the LLM fails after retries, `503` if the database is unreachable.

---

## 1.3 How to talk to the assistant (what it's good at)

The assistant acts as the agency's **first point of contact**, before the legal team. It handles questions like these well:

| Try asking | What it should do |
|---|---|
| "I work remotely, can I get a DTV?" | Confirm, then ask nationality and where they'll apply |
| "What documents do I need?" | List the documents for their DTV type |
| "Does crypto count for the bank balance?" | No; explain the 500,000 THB bank-account rule |
| "My DTV got rejected in Vietnam" | Ask for the rejection reason and DTV type (learned in v6) |
| "My tourist visa expires in 10 days!" | Acknowledge the urgency and give a concrete step-by-step plan |
| "I've uploaded everything" | Ask for their sign-up email so the team can find the account |

What it deliberately **won't** do:
- claim to see accounts, documents or payments;
- invent prices or rules it wasn't given;
- coach clients to hide information from an embassy.

Case-specific legal questions go to the legal team.

**Send the whole conversation each time.** The server doesn't remember previous calls; `chatHistory` is the memory.

---

## 1.4 Run it yourself

**You need:** Python 3.11+, a Gemini API key (free at aistudio.google.com) and, optionally, a Supabase project.

```bash
git clone <this repo> && cd <repo>
python -m pip install -r requirements-dev.txt
cp .env.example .env            # Windows: copy .env.example .env  → then fill it in
python -m pytest -q             # 22 offline tests, no keys needed
python wsgi.py                  # http://localhost:5000
```

**`.env`: the settings that matter**

| Setting | Value | Notes |
|---|---|---|
| `GEMINI_API_KEY` | your key | Required |
| `LLM_MODEL` | `gemini-3.5-flash-lite` | Used in production; fast, with a separate free quota. Check yours with `python scripts/check_llm.py` |
| `GEMINI_THINKING_LEVEL` | `low` | Faster replies |
| `SUPABASE_URL` / `SUPABASE_KEY` | project URL / `sb_secret_…` key | Leave both empty to use a local SQLite file instead |
| `ADMIN_TOKEN` | any long password | Protects rollback |
| `LLM_MIN_INTERVAL_SECONDS` | `4` while training | Keeps under free-tier rate limits |

**Supabase, one-time setup:** run [`schema.sql`](../schema.sql) in the SQL Editor. If the API says it can't find the table, run `notify pgrst, 'reload schema';`. The first request creates version 1 from `prompts/reply_seed.md`.

**Deploy to Render:** New → Blueprint → pick the repo (it reads `render.yaml`) → set the environment variables above. Paste values carefully, because a trailing space in a URL breaks it.

---

## 1.5 Training and evaluation commands

```bash
python scripts/analyze_data.py                         # dataset statistics
python scripts/question_distribution.py                # rebuild docs/question_distribution.xlsx
python scripts/check_llm.py                            # which models your key can use + speed test
python scripts/train.py --n 10 --balanced --dry-run    # preview edits, save nothing
python scripts/train.py --n 10 --balanced              # learn from 10 examples, all question types
python scripts/evaluate.py --versions 1 latest --n 8   # before/after report → docs/BEFORE_AFTER.md
```

Approximate free-tier cost: training uses about 2 LLM calls per example; evaluation about 4 per example.

---

## 1.6 Maintaining it (for the next lab member)

| I want to… | Do this |
|---|---|
| Change the bot's tone or a fact | `POST /improve-ai-manually` with plain-English instructions (try `dryRun` first) |
| Undo a bad change | `GET /prompt/history`, then `POST /prompt/rollback` with the good version number |
| See exactly what the bot learned | `GET /prompt/<n>` for two versions, or the `diff` in any improve response |
| Switch AI provider | Set `LLM_PROVIDER` (`gemini` / `anthropic` / `openai`) and its key. No code change |
| Change what self-learning may never learn | `prompts/editor_from_example.md` ("Never learn") and `FORBIDDEN_RULES` in `app/assistant.py` |
| Add a question type | Add a rule to `app/categories.py` (first match wins) |

**Code map**
```
app/__init__.py      HTTP routes, input validation, error handling
app/assistant.py     generate / improve logic, guardrails, diffs
app/conversation.py  dataset parsing, API input normalisation
app/categories.py    question-type rules, balanced sampling
app/llm.py           LLM client (Gemini / Claude / OpenAI-compatible / offline fake)
app/store.py         versioned prompt storage (Supabase or SQLite)
prompts/             the assistant's seed prompt, editor prompts, judge prompt
scripts/             analysis, training, evaluation, diagnostics, live test
tests/               22 offline tests (pytest)
```