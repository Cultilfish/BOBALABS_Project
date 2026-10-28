# AI usage log

_TODO: review and edit this so it reflects what you actually did. Add anything you changed, rejected or debugged yourself._

## Tools used
| Tool | Used for |
|---|---|
| Claude (Opus 5.5, claude.ai) | Understanding the brief, planning the architecture, analysing the dataset, writing the first version of the code, prompts, tests and docs |
| Gemini 2.5 Flash (API) | Runtime model: generates replies, edits the prompt, and judges the evaluation _(update if you used another)_ |
| _TODO_ | _e.g. Cursor for edits, ChatGPT for a second opinion_ |

## Key prompts and what came out of them

**1. Scoping**
> "Explain what i need to do, how I should do it, If i can do this"
> "I don't even have that much time. I have only 9 hours"

Claude reduced the brief to four requirements and a time plan, and advised cutting extras (Docker, frontend) in favour of one improvement that addresses a real weakness: prompt versioning with rollback.

**2. Architecture**
> "how would you plan to make this?" / "can you make a use case diagram for this"

This produced the two-prompt design (an editable reply prompt and fixed editor prompts), the append-only version table, guardrails on self-edits, and a train/test split by conversation.

**3. Data analysis** (conversations.json attached)

Claude wrote `scripts/analyze_data.py` and found:
- there is no ghosting in the data;
- consultant replies have a median of 36 words;
- an arithmetic error in the Laos fees (5,000 + 10,000 quoted as 18,000);
- replies that claim account access or coach clients on what to tell the embassy.

These shaped the seed prompt and the editor's "never learn" list.

**4. Implementation**

Claude wrote the Flask app, the LLM client, the store, the scripts and 20 offline tests. It ran the tests, ran the server under gunicorn and called every endpoint with cURL using a fake LLM provider.

## My contribution and verification
_TODO: fill in honestly. For example:_
- What I accepted as is: ...
- What I changed and why: ...
- What I rejected: ...
- How I checked it: ran `pytest`, tested the live endpoints with `docs/curl_examples.sh`, read through the training log and the prompt diffs, and compared before/after replies myself in `docs/BEFORE_AFTER.md`.

## Final application prompts
All prompts the application uses are in [`prompts/`](prompts/):
- `reply_seed.md` is version 1 of the reply prompt. Later versions are in the database, and you can see them at `GET /prompt/history`.
- `editor_from_example.md` is used by `/improve-ai`.
- `editor_from_instructions.md` is used by `/improve-ai-manually`.
- `judge.md` is used by the evaluation script.
