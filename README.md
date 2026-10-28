# Self-learning visa support assistant (BOBALAB technical assessment)

> **Brief Introduction** Greetings user. My name is Daniel Jeejo Nooranal from Robotics & AI and I have created an AI messaging agent that improves based on the training data provided for visa related questions. This is what the project is below.

A Flask microservice that answers Thai DTV visa clients the way the agency's human consultants do: short, warm, and always moving the client one step forward. It **improves itself** by comparing its replies with real consultant replies and editing its own prompt, with guardrails, full version history and measured before/after results.

| | |
|---|---|
| **Live server** | https://bobalab-visa-assistant.onrender.com (free tier: first request may take about 50s to wake) |
| **Prompt history** | https://bobalab-visa-assistant.onrender.com/prompt/history |
| **Model** | Gemini (`gemini-3.5-flash-lite`), chosen by benchmark; see [3.5](docs/3_IMPROVEMENTS_AND_RESULTS.md#35-engineering-problems-found-and-fixed-while-building) |
| **Database** | Supabase (Postgres), append-only prompt versions |

## Quick test

```bash
curl -s -X POST https://bobalab-visa-assistant.onrender.com/generate-reply \
  -H "Content-Type: application/json" \
  -d '{"clientSequence": "I'\''m American and currently in Bali. Can I apply from Indonesia?",
       "chatHistory": [
         {"role": "client", "message": "Hello, I'\''m interested in the DTV visa. I work remotely for a US company."},
         {"role": "consultant", "message": "Hi there! May I know your nationality and which country you'\''d like to apply from?"}]}'
```
Example response (captured from the live server):
```json
{"aiReply": "Yes, you can apply from Indonesia! ... To start, download our app, create an account, and upload your documents for a free review by our legal team. What email will you use to sign up?", "promptVersion": 1}
```

cURL for **all three endpoints** with expected responses: [docs/1_SETUP_AND_USAGE.md § 1.2](docs/1_SETUP_AND_USAGE.md#12-the-three-endpoints-requests-and-expected-responses) and [`docs/curl_examples.sh`](docs/curl_examples.sh). On Windows: `powershell -ExecutionPolicy Bypass -File scripts\test_live.ps1`.

---

## Documentation map

| Read this | For |
|---|---|
| **This README** | Overview, headline results, contribution summary |
| [1 · Setup and usage](docs/1_SETUP_AND_USAGE.md) | Running it, configuration, all endpoints, how to talk to the assistant, maintenance guide |
| [2 · Findings](docs/2_FINDINGS.md) | Use case diagram, question-type distribution ([spreadsheet](docs/question_distribution.xlsx)), data problems |
| [3 · Improvements and results](docs/3_IMPROVEMENTS_AND_RESULTS.md) | What was added, balanced training, before/after results, strengths and weaknesses |
| [AI_USAGE.md](AI_USAGE.md) | AI tools used, key prompts, what I accepted, changed or rejected |
| [prompts/](prompts/) | The application's final prompts (seed, editors, judge) |

---

## How it works

```
POST /generate-reply ─────► load active prompt (Supabase) ─► Gemini ─► {"aiReply"}

POST /improve-ai ─────────► 1. predict a reply with the current prompt
                            2. editor LLM compares it with the REAL consultant reply
                            3. editor proposes the smallest prompt edit + diagnosis
                            4. guardrails check ──✗──► rejected, nothing saved
                            5. ✓ saved as a NEW version (old versions kept, rollback possible)

POST /improve-ai-manually ► same flow, driven by a reviewer's plain-English instructions
```

- **Two kinds of prompt.** The reply prompt (in the database) learns. The editor prompts (in code) are fixed, so the system can't rewrite its own learning rules.
- **Self-learning can't break the API.** The "return JSON" instruction is appended in code, outside the editable prompt.
- **Guardrails** reject edits that bloat or truncate the prompt, drop sections, copy data placeholders, or teach forbidden behaviour such as claiming account access or coaching clients to mislead an embassy.
- **Every edit returns a diff and a diagnosis**, and `"dryRun": true` previews an edit without saving it.

## Headline results

Trained prompt (v9) against the original seed (v1), on 8 held-out turns from conversations never used in training, scored 1–5 by an LLM judge:

| | v1 seed | v9 trained |
|---|---:|---:|
| Overall | 3.88 | **4.12** |
| Content (right facts) | 4.12 | 4.38 |
| Next step (moves client forward) | 3.88 | **4.25** |
| Style / sounds human | 4.12 / 4.12 | 4.12 / 4.12 |

This is a positive direction on a small sample (3 turns better, 2 worse, 3 the same), not proof. Details, worked examples and caveats: [docs/3 § 3.4](docs/3_IMPROVEMENTS_AND_RESULTS.md#34-test-results-before-vs-after).

---

## Contribution summary

**Key decisions**
- **Category-balanced training, adapted from my YOLO work in the I² (Intania Square) Hackathon.** Rare but important situations, like visa rejections (2.3% of the data), were being drowned out by common ones. Training now picks examples evenly across all 13 question types, which raised coverage from 7 to 13 types.
- **Question-type distribution analysis.** I wanted to see what clients actually ask about, and whether the data was imbalanced, before deciding how to train. It showed that the three most common types make up 35% of the data while the rarest are under 4% ([spreadsheet](docs/question_distribution.xlsx)).
- **Choosing the model by benchmark, not by default.** `gemini-3.8-flash` timed out even on a one-word test, so I benchmarked the available models and chose `gemini-3.5-flash` (about 2s). I moved to `gemini-3.5-flash-lite` when its free daily quota ran out.
- **Reliability before extras.** Due to restricted time, I deliberately left out optional extras such as Docker and a frontend. I focused on making the required workflow reliable, testable and safe to self-edit (guardrails, versioning and rollback).

**Use of AI tools**
- Claude wrote most of the code and the first drafts of the documentation. I directed the design, contributed the balanced-training and question-analysis ideas, carried out the setup, deployment and debugging, and checked the results myself: tests, live endpoints, every learned prompt change and the per-example evaluation scores. Full details: [AI_USAGE.md](AI_USAGE.md).

**Known limitations**
- Small evaluation (8 held-out turns) because of the free-tier quota, scored by a judge from the same model family as the assistant.
- Rare question types (interviews, eligibility, rejections) appear only in the training data, so the evaluation can't measure them.
- The prompt learns from one example per edit, so edits can over-correct; facts live in the prompt rather than a maintained knowledge base.
- The free Render instance sleeps when idle, so the first request can take about 50 seconds.

**Unfinished**
- A validation gate that accepts a prompt edit only if held-out scores don't drop. It's designed, but not built.
- Evaluation on all 43 held-out turns, with a judge from a different model provider.
- Data augmentation: reworded variations of rare questions, to give the system more examples of uncommon situations.
- A small web interface showing the prompt version timeline and the diff of each change.

---

## Project layout

```
app/          Flask app: routes, assistant logic + guardrails, LLM client, prompt store, question types
prompts/      reply_seed.md (v1), editor_from_example.md, editor_from_instructions.md, judge.md
scripts/      analyze_data, question_distribution, train, evaluate, check_llm, test_live.ps1
tests/        22 offline tests (python -m pytest -q)
docs/         the three documents above, spreadsheet, generated before/after report, cURL examples
data/         conversations.json (sample data provided)
schema.sql    Supabase table · render.yaml  Render deploy · .env.example  settings template
```
