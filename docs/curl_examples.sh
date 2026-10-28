#!/usr/bin/env bash
# Example requests for every endpoint. Usage:
#   BASE=https://your-app.onrender.com bash docs/curl_examples.sh
# Note: the free Render instance sleeps when idle, so the first request can take ~30-50 s.
BASE=${BASE:-http://localhost:5000}

echo "== 1. POST /generate-reply =="
curl -s -X POST "$BASE/generate-reply" \
  -H "Content-Type: application/json" \
  -d '{
    "clientSequence": "I'\''m American and currently in Bali. Can I apply from Indonesia?",
    "chatHistory": [
      {"role": "client", "message": "Hello, I'\''m interested in the DTV visa for Thailand. I work remotely as a software developer for a US company."},
      {"role": "consultant", "message": "Hi there! Thank you for reaching out. The DTV (Destination Thailand Visa) is perfect for remote workers like yourself. May I know your nationality and which country you'\''d like to apply from?"}
    ]
  }'
# Expected: {"aiReply": "Yes, you can apply from Indonesia! ...", "promptVersion": 1}
echo; echo

echo "== 1b. Multiple client messages, history given newest-first (as in the brief's example) =="
curl -s -X POST "$BASE/generate-reply" \
  -H "Content-Type: application/json" \
  -d '{
    "clientSequence": ["Ok thanks", "Also does crypto count for the bank balance?"],
    "historyOrder": "newest_first",
    "chatHistory": [
      {"role": "consultant", "message": "For remote workers our service fee is 18,000 THB including government fees."},
      {"role": "client", "message": "How much does it cost?"}
    ]
  }'
echo; echo

echo "== 2. POST /improve-ai (learn from a real consultant reply) =="
curl -s -X POST "$BASE/improve-ai" \
  -H "Content-Type: application/json" \
  -d '{
    "clientSequence": "I'\''m American and currently in Bali. Can I apply from Indonesia?",
    "chatHistory": [
      {"role": "client", "message": "Hello, I'\''m interested in the DTV visa for Thailand. I work remotely as a software developer for a US company."},
      {"role": "consultant", "message": "Hi there! Thank you for reaching out. The DTV is perfect for remote workers like yourself. May I know your nationality and which country you'\''d like to apply from?"}
    ],
    "consultantReply": "Yes, absolutely! You can apply at the Thai Embassy in Jakarta. I'\''d recommend scheduling an appointment soon as slots fill up quickly."
  }'
# Expected: {"predictedReply": "...", "diagnosis": "...", "changeSummary": "...",
#            "previousVersion": 1, "updated": true, "updatedPrompt": "...", "version": 2, "diff": "--- current ..."}
# Add "dryRun": true to see the proposed edit without saving it.
echo; echo

echo "== 3. POST /improve-ai-manually =="
curl -s -X POST "$BASE/improve-ai-manually" \
  -H "Content-Type: application/json" \
  -d '{"instructions": "Be more concise. Always mention appointment booking proactively."}'
# Expected: {"changeSummary": "...", "previousVersion": 2, "updated": true, "updatedPrompt": "...", "version": 3, "diff": "..."}
echo; echo

echo "== Extras: inspect and roll back prompt versions =="
curl -s "$BASE/prompt/history"; echo
curl -s "$BASE/prompt"; echo
# Restore version 1 (needs the ADMIN_TOKEN configured on the server):
# curl -s -X POST "$BASE/prompt/rollback" -H "Content-Type: application/json" \
#   -H "X-Admin-Token: $ADMIN_TOKEN" -d '{"version": 1}'
