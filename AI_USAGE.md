# AI usage log

## 1. Tools used

| Tool | What it helped with |
|---|---|
| **Claude** (Anthropic, Opus 5.5, in the Claude app) | Understanding the brief, time planning, architecture, use case diagram, data analysis, writing the code, tests and first drafts of the docs, step-by-step help with setup and debugging |
| **Gemini API** (`gemini-3.5-flash`, then `gemini-3.5-flash-lite`) | The running application: generating replies, editing the prompt, judging the evaluation |
| **VS Code + PowerShell** | Running, testing and deploying the code |

## 2. How I used AI, and why

For this project I used AI (Claude) to significantly reduce the time needed to build and deploy the assistant. I decided the setup work would be done more efficiently with AI support, as it included understanding and navigating the platforms involved, such as Supabase and Render, and writing most of the code files that connect to them. However, this did not mean handing the work over blindly. While delegating work, I made sure I understood what each step was doing, carried out the setup and deployment myself, and debugged problems as they came up, such as database connection errors, a model that kept timing out, and a configuration mistake on Render.

Once the basic system was working, I began brainstorming ways to make the assistant's learning more effective. I took inspiration from a technique I used in the I² (Intania Square) Hackathon, where my team detected liver tumours in ultrasound images with YOLO. There, I made extra copies of the rare cancer examples so the model would not ignore them.

To check whether this dataset had the same problem, I first had the AI build a spreadsheet showing which types of client questions are most and least common in the sample conversations BOBALAB provided. It showed a clear imbalance: rejections make up only 2.3% of the data and eligibility questions 3.1%, while the three most common types make up 35%. My first idea was to copy the rare questions, as I had with YOLO. However, I learned that this does not transfer to prompt-based learning. Each example produces one edit to the prompt, so a duplicate would just repeat the same edit and waste API quota. Instead, I kept the idea behind it, giving rare cases an equal voice, and changed the method: training now picks existing examples evenly across all 13 question types, rarest first, without duplicates. This raised coverage from 7 of 13 question types to all 13, and the second training run produced lessons about rejections, payment problems and eligibility that the first run never reached.

One problem was Gemini's free-tier limits. The model I first chose from my benchmark, `gemini-3.5-flash`, ran out of its daily quota partway through training. To work around this, I switched to `gemini-3.5-flash-lite`, a smaller and faster model with its own separate quota. That allowed training and evaluation to finish, but it also meant keeping the evaluation small (8 held-out examples), which I note as a limitation.

To check the AI's work, I ran the automated tests, tested every endpoint on my machine and on the live server, read through each of the prompt changes the system learned, and looked at the individual before-and-after scores rather than only the average.

With more time, I would try the other half of my original idea: creating reworded variations of the rare questions (data augmentation) to give the system more examples of uncommon situations.

## 3. Key prompts and what came out of them

These are my actual prompts (lightly trimmed), in order, with what the AI produced and what I did with it.

## 3. Key prompts and what came out of them

The prompts below are **summarised for readability**. The meaning of each is unchanged, with typos and casual phrasing cleaned up. They are listed in order, with what the AI produced and what I did with it.


**1. Design before code**
> **Prompts:** How would you plan and structure this system? → Create a use case diagram for it. → Turn that into a spreadsheet.

**Result:** the architecture (an editable reply prompt in the database and fixed editor prompts in code), the use case diagram ([docs/2 § 2.1](docs/2_FINDINGS.md#21-how-the-system-works-use-case-diagram)) and a use-case table.

**2. Building from the real data**
> **Prompt:** *(uploaded the sample data, `conversations.json`)*

**Result:** the AI analysed the data first, then wrote the code. The findings: consultant replies have a median of 36 words; there's no ghosting in the data; a fee arithmetic error (5,000 + 10,000 quoted as 18,000); and replies claiming account access the bot doesn't have. These shaped the seed prompt and the guardrails.

**3. Setup and debugging** (most of the session)
> **Prompt (summarized):** Questions about configuring Supabase and the environment settingsm, plus the error messages I hit at each stage, shared for diagnosis.

**Result:** working local and live deployments. Problems solved along the way:
- the new Supabase key format;
- a missing table and the API's schema cache;
- my keys typed into `.env.example` instead of `.env`;
- a retired Gemini model;
- `gemini-3.8-flash` timing out, which led to a diagnostic script and a benchmark of 4 models;
- a trailing space in the Render URL;
- running out of daily quota;
- a Windows Thai code page crash.

**4. My training idea**
> **Prompt:** Due to the sample question distribution in the conversation json, create extra copies of questions with minor changes such as word edits without changing their meaning. This new distribution should even out all question error preventing the training model to have insufficient data on certian questions.

**Result:** the AI explained why literal copies don't transfer to prompt learning (a duplicate just repeats the same edit), and proposed **category-balanced sampling** instead. It also built question-type labelling and the spreadsheet. Coverage went from 7 of 13 question types to 13 of 13.

**5. Testing**
> **Prompt:** How can I test this system end to end?

**Result:** a three-level test plan: offline unit tests, a live end-to-end PowerShell test of every endpoint, and the held-out before/after evaluation.

## 4. My contribution: accepted, modified, rejected, verified

**Accepted**
- The overall architecture, guardrails and versioning design.
- Writing the seed prompt from patterns measured in the sample data, rather than a generic assistant prompt.

**Modified / redirected**
- **Training data selection.** I proposed oversampling rare cases (from YOLO). The AI's first training script picked examples evenly and never reached rare cases like rejections.
- **Model choice.** The AI's default (`gemini-2.5-flash`) was retired and the next suggestion (`gemini-3.8-flash`) timed out. I benchmarked the models and switched to `3.5-flash`, then to `3.5-flash-lite` when the quota ran out. I updated the default model in `app/llm.py` and the settings in `.env` and on Render myself.

**Rejected**
- **Literal duplication of examples.** It was my own first idea, and I dropped it after understanding it would only repeat the same edit and waste quota.

**How I checked the results**
- Ran the offline test suite locally (`python -m pytest -q`).
- Tested every endpoint on my machine, then on the live Render server.
- Read all 8 prompt edits in `/prompt/history` and judged whether each was a sensible lesson.
- Ran the held-out evaluation and checked the per-example scores, including the 2 regressions, rather than only the average.

## 5. Final application prompts

All the prompts the running application uses are in [`prompts/`](prompts/):

| File | Used by |
|---|---|
| `reply_seed.md` | Version 1 of the assistant's prompt. Later versions are in the database: `GET /prompt/history` |
| `editor_from_example.md` | `POST /improve-ai`: diagnoses the difference and makes a minimal edit, with a "never learn" list |
| `editor_from_instructions.md` | `POST /improve-ai-manually` |
| `judge.md` | `scripts/evaluate.py`: scores replies 1–5 against the real consultant |

No API keys, credentials or personal data are included in this repository.