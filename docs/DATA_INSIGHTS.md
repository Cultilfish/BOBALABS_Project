# What the sample data says

Produced with `python scripts/analyze_data.py`. These findings shaped the seed prompt (`prompts/reply_seed.md`), the editor guardrails and the evaluation.

## Shape
- 15 conversations (all synthetic, `SYNTH_001` to `SYNTH_015`), each a different scenario: remote worker, Muay Thai, cooking class, freelancer, rejection, post-approval, payment problems, interview prep, urgent case, and so on.
- 128 training examples once consecutive messages are grouped into client sequences followed by consultant replies. Only 2 examples have multi-message client sequences, which still need handling because the API accepts 1+ messages.
- One conversation (`SYNTH_012`) is started by the consultant (a follow-up about an embassy document request), so history can begin with a consultant message.
- 4 client messages are attachments (`[Non-text message]`). These are mapped to a readable placeholder so the model knows a file was sent.

## How the real consultants write
| Signal | Value | What I did with it |
|---|---|---|
| Reply length | median 36 words (14-67) | Prompt targets 15-60 words and allows longer only for lists |
| Numbered or bulleted lists | 33% of replies | Lists only for 3+ documents, options or steps |
| Asks the client a question | 18% | At most 1-2 questions, and only when info is missing |
| Emoji | 4% | At most one, for celebrations or encouragement |
| First word | "Yes", "For", "You're", "Hello", "Great" | Answer the question in the first sentence |

The consultants are friendly and clear rather than slangy. "Human and casual" here means short, direct and warm, not lowercase texting. The prompt targets that register.

## What clients ask about
Fees, where to apply, documents, processing time, the 500,000 THB balance rule, soft-power options (Muay Thai, cooking), post-approval logistics (TDAC, 90-day reporting, re-entry), interviews and rejections.

## High-intent signals
- Says they downloaded the app, signed up or are uploading (6/15 conversations)
- Gives a timeline or urgency, such as a visa expiring or "tonight" (8/15)
- Asks "how do I start?" or "what's the first step?" (4/15)
- Pays or sends a receipt (3/15), or already has documents ready (2/15)

In the data, the consultant responds to these by moving straight to the next concrete step: app, then email, then review, then payment. The prompt encodes that funnel, including asking for the sign-up email once the client is ready.

## Drop-offs and ghosting
**There are none in this dataset.** All 15 conversations end with a consultant message, and no client sequence goes unanswered. So I can't learn ghosting patterns from this data, and I say so rather than invent them. With real data, I'd count conversations where the last message is from the consultant and the client never replied. Then I'd compare what that last consultant message looked like (a long list? no question? a price quote?) against conversations that continued.

## Problems in the data the bot should *not* learn
1. **Arithmetic error.** Three conversations (`SYNTH_003`, `SYNTH_010`, `SYNTH_014`) quote Laos as a 5,000 THB service fee plus a 10,000 THB government fee, then call that a "total of 18,000 THB". 5,000 + 10,000 = 15,000. The seed prompt states the two fees without a total, and the editor is told never to learn facts that don't add up.
2. **Claims of system access.** Consultants say "I found your account" and "Payment received", but the bot has no account or payment access. If it learned these lines, it would make false claims. They are blocked in the editor prompt and by a regex guardrail.
3. **Coaching what to tell the embassy.** Some replies advise leaving Thai clients out of the application or interview. The bot sits before the legal team, so that kind of advice is risky. The prompt routes it to the legal team, and the editor won't learn it.
4. **Placeholders** such as `[APP_LINK]`, `[EMAIL]` and `[BANK_NAME]`. These are anonymisation artefacts, and the guardrail rejects prompt edits that copy them in.
5. **Synthetic facts.** Prices, timelines and approval rates come from synthetic data, so they shouldn't be treated as real immigration rules. The bot is told to defer to the legal team whenever it isn't sure.
