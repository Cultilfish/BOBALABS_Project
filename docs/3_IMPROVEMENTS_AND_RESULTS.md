# 3. What was added, how it was trained, and the results

This document covers the improvements made beyond the basic brief, how the training data was chosen, the before/after test results, and an honest list of strengths and weaknesses.

- Generated evaluation report: [`BEFORE_AFTER.md`](BEFORE_AFTER.md)
- Question-type data: [`question_distribution.xlsx`](question_distribution.xlsx)

---

## 3.1 Improvements beyond the basic brief

| # | Improvement | Problem it solves | Where |
|---|---|---|---|
| 1 | **Output format kept outside the editable prompt** | A self-edit could delete the "return JSON" instruction and break the API | `app/assistant.py` `OUTPUT_CONTRACT` |
| 2 | **Append-only prompt versions + rollback** | A bad self-edit would otherwise overwrite the good prompt with no way back | `app/store.py`, `GET /prompt/history`, `POST /prompt/rollback` |
| 3 | **Guardrails on self-edits** | Learning from raw human replies would copy real mistakes found in the data (section [2.6](2_FINDINGS.md#26-problems-in-the-data-the-bot-must-not-learn)) | `check_prompt_edit()` |
| 4 | **Diff, diagnosis and dry-run on every edit** | Reviewers need to see *what* was learned and *why* before trusting it | `/improve-ai` response |
| 5 | **Category-balanced training** | Rare but risky situations were never trained on | `app/categories.py`, `train.py --balanced` |
| 6 | **Held-out evaluation with an LLM judge** | "It seems better" isn't evidence | `scripts/evaluate.py` |
| 7 | **Model benchmarking script** | The default model was timing out; choosing a model needed data | `scripts/check_llm.py` |
| 8 | **Provider-agnostic LLM client** | Free-tier quotas run out; switching provider is one setting | `app/llm.py` |

### The guardrails in detail
An automatic edit is **rejected and not saved** if it:
- grows the prompt by more than ~25% in one step (overfitting to one example), or shrinks it by more than 30% (truncation);
- removes a section heading (structure drift);
- copies a placeholder token such as `[APP_LINK]` from the data;
- teaches a forbidden behaviour, such as "I found your account", "payment received", or "don't tell the embassy";
- exceeds the maximum prompt length.

Manual edits from a reviewer are trusted more and only get the safety checks, not the size checks.

**Which improvement matters most.** In my view, the guardrails and prompt versioning (improvements 2 and 3) matter most. A self-learning system is a feedback loop: it changes its own behaviour based on what it observes, and in robotics and control engineering you would never let a system retune itself without limits on how far it can change and a way to return to a known-good state. The guardrails provide those limits by rejecting edits that are too large or that teach unsafe behaviour, and versioning with rollback provides the safe state to return to, which makes it reasonable to let the assistant keep learning in production.

---

## 3.2 How the data was used for training (balanced sampling)

### How "training" works here
Nothing is trained in the machine-learning sense. Per the brief, **the prompt is what learns**. For each training example:

1. Generate a reply with the current prompt.
2. An editor LLM compares it with the real consultant's reply and diagnoses the most important difference.
3. The editor proposes the **smallest edit** to the prompt that would fix that kind of difference.
4. The guardrails check the edit. If it passes, it's saved as a new version; if not, it's rejected and logged.

### The idea: oversampling rare cases, adapted from YOLO
In the I² (Intania Square) Hackathon, my team MedViz built a YOLO model to detect liver tumours in ultrasound images. The cancer examples were much rarer than the rest of the data, so I made several copies of each one; otherwise the model would mostly learn the common cases and tend to miss the rare ones that mattered most. When I looked at the question-type distribution for this project, I saw the same problem: visa rejections make up only 2.3% of the client turns and eligibility edge cases 3.1%, and the original training selection never reached them at all. However, copying examples doesn't transfer directly to this system. In YOLO, a duplicate adds weight to its class during training, but here each example triggers one discrete edit to the prompt, so a duplicate would just repeat the same edit (or produce "no change") and waste API quota. I therefore kept the idea, giving rare cases an equal voice, but changed the method: training now picks existing examples round-robin across all 13 question types, rarest first, with no duplicates.

### What balancing changed

| Selection method (15 examples) | Question types covered |
|---|---:|
| Even spread across the data (original) | **7 / 13** (no rejections, payments, fees, timelines or eligibility) |
| Category-balanced (`--balanced`) | **13 / 13** |

The Summary sheet of [`question_distribution.xlsx`](question_distribution.xlsx) has a chart comparing both selections type by type.

---

## 3.3 What the system actually learned (prompt history)

Training ran in two batches. The first batch, an even spread on `gemini-3.5-flash`, stopped after 3 edits when the model's daily free quota ran out. The second batch, balanced with 10 examples on `gemini-3.5-flash-lite`, produced 5 edits and 5 "no change" results.

| Version | Source | What the editor changed |
|---|---|---|
| v1 | seed | Initial prompt written from the data analysis |
| v2 | auto | The 500,000 THB balance must be kept until approval, as embassies may ask for an updated statement |
| v3 | auto | Invite clients to upload existing documents now for a free review, even if something isn't ready yet |
| v4 | auto | Added passport photo requirements to the facts |
| v5 | auto (balanced) | On payment trouble, ask what the problem is instead of assuming account access |
| v6 | auto (balanced) | On a rejection, ask for the rejection reason and the DTV type |
| v7 | auto (balanced) | Ask a clarifying question on borderline or case-specific legal questions |
| v8 | auto (balanced) | Mention the money-back guarantee rule when clients ask about staying in the submission country |
| v9 | auto (balanced) | Added Laos interview questions to the facts |

No edit was blocked by the guardrails in these runs. My manual review below found one edit (v9) that over-generalised from a single conversation, a case the guardrails are not designed to catch.

I read the full text of version 9 and compared it with the seed. All eight edits were placed in the right sections, kept the structure intact and are written as general rules. For example, on a rejection the assistant now expresses sympathy and asks for the embassy's reason and the DTV type. However, my review found three issues the guardrails did not catch. v9 over-generalised from a single Muay Thai conversation, stating that the Laos interview asks "why you want to train", which would mislead a remote worker. v8 duplicated the money-back guarantee rule that already existed in the facts section. And v5 appended the payment rule onto an unrelated line. I would fix v9 with a manual edit (`POST /improve-ai-manually`, stating that interview questions depend on the DTV type). These issues show why learning from one example per edit needs a human review step or a validation gate.

## 3.4 Test results: before vs after

**Method.** For each of 8 held-out turns (conversations `SYNTH_011`–`015`, never used in training), the system generated a reply with **v1** (seed) and with **v9** (trained). An LLM judge (`prompts/judge.md`) scored each reply from 1 to 5 against the real consultant reply. Command: `python scripts/evaluate.py --versions 1 latest --n 8`.

| Metric | v1 (seed) | v9 (trained) | Change |
|---|---:|---:|---:|
| Content: right facts, nothing invented | 4.12 | 4.38 | +0.25 |
| Next step: moves the client forward | 3.88 | 4.25 | **+0.38** |
| Style: length, tone, format | 4.12 | 4.12 | 0 |
| Human: doesn't sound like a bot | 4.12 | 4.12 | 0 |
| **Overall** | **3.88** | **4.12** | **+0.25** |
| Median words (human consultant: 32) | 38 | 36 | closer to human |
| Robotic phrases ("happy to assist", ...) | 0 | 0 | |

**Per example (overall score):**

| Turn | v1 | v9 | |
|---|---:|---:|---|
| SYNTH_011 (a) | 4 | 4 | same |
| SYNTH_011 (b) | 4 | 3 | worse |
| SYNTH_012 (a) | 3 | 4 | better |
| SYNTH_012 (b) | 4 | 4 | same |
| SYNTH_013 | 4 | 5 | better |
| SYNTH_014 (a) | 5 | 4 | worse |
| SYNTH_014 (b) | 5 | 5 | same |
| SYNTH_015 (urgent case) | 2 | 4 | **better** |

### Worked examples
The full replies for every turn (the client message, the v1 reply, the v9 reply, the real consultant reply and the judge's reasoning) are in [`BEFORE_AFTER.md`](BEFORE_AFTER.md), together with the complete prompt diff from v1 to v9.

- **Biggest improvement: SYNTH_015, the urgent case (2 → 4).** This is the largest gain in the evaluation, on the kind of time-pressured conversation where a concrete next step matters most.
- **Regressions: SYNTH_011 (b) (4 → 3) and SYNTH_014 (a) (5 → 4).** Each dropped by one point. With a single run per example, a one-point swing can come from normal variation between replies, so I don't read these as clear evidence that an edit made things worse. A repeated or larger evaluation would separate real regressions from noise.

### Verdict: did the change improve the result?
On 8 held-out turns, the trained prompt (v9) scored higher than the seed overall (3.88 → 4.12). The gains were in content (+0.25) and next-step behaviour (+0.38), which are exactly the areas the learned edits targeted, while style and human-ness stayed the same because the seed prompt already sounded natural (zero robotic phrases in both versions). Replies also moved slightly closer to the human consultants' length (38 → 36 words, against 32). However, 3 turns improved, 2 got worse and 3 stayed the same, so I treat this as a positive signal rather than proof: the sample is small, the judge comes from the same model family as the assistant, and replies vary between runs. A larger evaluation with an independent judge would be needed to confirm it.

---

## 3.5 Engineering problems found and fixed while building

| Problem | How it showed up | Fix |
|---|---|---|
| `gemini-2.5-flash` retired for new users | HTTP 404 on the first call | Moved to a current model |
| `gemini-3.8-flash` unusable on the free tier | Timed out after 45s even on a one-word "ping" | Wrote `check_llm.py` and benchmarked the models the key can use: `3.5-flash` 1.9s, `3.5-flash-lite` 1.4s, `flash-lite-latest` 1.9s, `flash-latest` timed out |
| Daily free quota used up mid-training | HTTP 429 "exceeded your current quota" | Switched to `gemini-3.5-flash-lite`, which has a separate quota and answers in 1.1s, and reduced batch sizes |
| Slow "thinking" models hit server timeouts | Requests took over 60s | Added `GEMINI_THINKING_LEVEL=low`, shorter LLM timeouts, gunicorn timeout 180s |
| New Supabase key format (`sb_secret_…`) | Key isn't a JWT | Send it in the `apikey` header only |
| New table not visible to the API | `PGRST205 … schema cache` | `notify pgrst, 'reload schema'` |
| Trailing space in `SUPABASE_URL` on Render | "Host contains invalid character" | Removed the space; code now strips whitespace |
| Windows Thai code page (cp874) | Crash saving logs containing emoji | All result files written as UTF-8 |

The problem I am most proud of solving is the model timeouts. When the assistant kept failing, it wasn't clear whether the cause was my code, my settings or the model itself. A one-word test request also took over 45 seconds, which showed the problem was the model, not the prompt or the code. I then benchmarked the models available on my key instead of guessing: two timed out, while `gemini-3.5-flash` answered in about 2 seconds. When that model later ran out of free quota, the same benchmark let me switch straight to `gemini-3.5-flash-lite` (1.1s) without losing time.

---

## 3.6 Strengths, weaknesses and limitations

**Strengths**
- Self-learning **can't break the API**, because the output format lives in code, not in the editable prompt.
- **Every change is auditable and reversible**: version history, diff, diagnosis and the example that caused it.
- Learning is **filtered**: real mistakes in the data, such as the fee arithmetic and false account claims, are blocked.
- **Rare situations are covered** by balanced training.
- Improvement is **measured on held-out data**, not eyeballed.
- Works with Gemini, Claude or any OpenAI-compatible API by changing one setting.

**Weaknesses and limitations**
- **Small evaluation.** 8 turns, limited by the free-tier quota. The result is a direction, not proof.
- **Same-family judge.** The judge and the reply model are both Gemini, which can bias scores. `JUDGE_PROVIDER` allows a different judge.
- **Untested rare types.** Interviews, eligibility and rejections appear only in training data, so the held-out set can't measure them.
- **One example per edit.** Edits can over-correct or undo each other; my review found v9 over-generalised from a single conversation. Batching several examples per edit would be steadier.
- **Facts are in the prompt.** Prices and rules come from synthetic data and would go stale. A real deployment needs a knowledge base owned by the legal team.
- **Keyword labelling is approximate.** Each turn gets one type; a message about both fees and documents gets only the first match.
- **Free hosting.** Render sleeps when idle, so the first request takes about 50 seconds.
- The learning endpoints are **open** so reviewers can test them. In production, set `PROTECT_EDIT_ENDPOINTS=true`.

**Unfinished / next steps**
1. **Validation gate:** only accept a prompt edit if scores on held-out examples don't drop. It's designed, but not built in the time available.
2. **Human review step for learned edits:** my own review found v9 over-generalised from one conversation. I'd correct it with a manual edit and require approval before auto-edits go live.
3. **Larger, independent evaluation:** all 43 held-out turns, scored by a judge from a different model provider.
4. **Batch learning:** learn from several examples per edit, so one unusual conversation can't over-steer the prompt.
5. **Data augmentation:** reworded variations of rare questions, to give the system more examples of uncommon situations.
6. **A small web interface** showing the prompt version timeline and the diff of each change.
7. **Drop-off analysis** once real conversations, including ones where clients stopped replying, are available.
