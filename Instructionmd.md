# BOBALAB — Technical Take-Home Assessment 🧠

Welcome to the technical assessment by **BOBALAB — Berkeley Operations and Behavioral Analytics Lab**. We bring together students and researchers to explore AI, human decision-making, and practical applications through research, games, experiments, and projects.

We’re recruiting founding members for **Technology and Lab Operations** to help build the tools and systems behind our Thailand team. We’re looking for technical ability, initiative, and people who take ownership of their work.

This assessment uses a **visa customer-support scenario** to evaluate how you approach an unfamiliar problem and turn it into a working AI application.

## 🌟 Your Project

Build a **self-learning AI assistant that can respond to customer messages**—helping them early through the visa process, before they receive support from the legal team, and improving through every conversation.

It’s now possible for (Cursor/Antigravity + Opus 4.5/Gemini 3) to deliver work in hours that would take even senior engineers much longer without AI. That’s why we treat Cursor, Antigravity, Gemini, and ChatGPT as the default benchmark. You should have a working project within an hour and then refine beyond. Your project should outperform what you’d get by simply prompting (Cursor/Antigravity) with this description. We want to see the parts that only you—not the model—can contribute.

## What We Look For

We care about **how you think, what you build, and the contribution you can make**, beyond what appears on your résumé.

### ✅ You Are:

- **Curious** — You investigate unfamiliar problems and question how things work.
- **Collaborative** — You communicate clearly, welcome feedback, and support your teammates.
- **Proactive** — You take ownership, work through obstacles, and follow through.
- **Thoughtful** — You make deliberate decisions, test your work, and recognize its limitations.

## 🛠️ Assignment Prompt

**Build an Self-learning AI Assistant for Customer Support**

### Input:

We’ve included a file with sample data: `conversations.py`  
This contains sample messages with customers

### Use it to:

- Understand common visa questions and issues
- Identify signals of high-interest customers
- Spot patterns in drop-offs or ghosting
- Anything else that will help build a useful assistant

### Requirements:

- Use Cursor/Antigravity and LLMs of your choice - Claude, Gemini, and ChatGPT
- Create a microservice that takes in (1+ client messages) with the conversation history -- and responds intelligently by API call with LLM (ChatGPT, Claude, Gemini, etc)
- But responses **must not sound like an AI** — make it human, casual, similar to the sample chat data
- The AI is self-learning and trains on sample data to improve. You have a base 

(You don't have to use Python - but for the rest of this project description, I'm going to describe a Python-based system)

## 1️⃣ How to Get Started

1. Get API keys to free tiers for LLMs - Google (Gemma 2 API, Gemini API), Groq API (Llama, Mistral), Claude API
2. Set up a database and get API keys - Supabase, Neon, and Firestore all have free tiers
3. Download Cursor - Cursor has a free tier with 50 prompts and then after that, you can use API keys above to continue usage
4. (Alternatively, you can use Google Antigravity)
5. You will use Claude + ChatGPT on a browser to understand systems and ideas, and Cursor/Antigravity to update the code itself
6. Set up a basic Flask server (just returns hello world) and host it on Render or Railway.app or Fly.io

(If you want to have a frontend visualization, I recommend Next.js hosted on Vercel)

## 2️⃣ Prompts to Create Your Microservice

In the project, have an .env file with your API keys. 
Then open Cursor/Antigravity in your project (a basic Flask server with .env file with keys) and try putting the following in:

### CURSOR PROMPT 1:

`conversations.json` represents DM text exchange between clients ("in" messages) and immigration consultants ("out" messages). Clients send 1+ DM sequence followed by consultant's 1+ DM sequence reply. Create a script that reads in the json data to create a list of (client sequence + consultant sequence reply + preceeding chat history) for all of the client sequences. Each conversation may have multiple client sequences. Then print out a sample for testing purposes.

### BROWSER PROMPT 1:

(Switch over to Claude broswer, attach conversations.json and then prompt it, then copy this prompt back into Cursor)

`conversations.json` represents DM text exchange between clients ("in" messages) and immigration consultants ("out" messages). Clients send 1+ DM sequence followed by consultant's 1+ DM sequence reply. Generate a prompt for LLM that takes in a client sequence + preceeding chat history and returns an appropriate AI chatbot reply in json format, eg {"reply": "reply goes here"}

### CURSOR PROMPT 2:

[Copy the above generated prompt here]

This is a prompt for LLM that takes in a client sequence + preceeding chat history and returns an appropriate chat AI reply in json format. Update the script to use [YOUR LLM OF CHOICE through API KEY IN ENV] with this prompt to generate AI replies given client sequences + preceeding chat history. Then print out a few samples. 

Example: 

CLIENT:

- I'm American and currently in Bali. Can I apply from Indonesia?

CHAT HISTORY:

- (CONSULTANT) Hi there! Thank you for reaching out. The DTV (Destination Thailand Visa) is perfect for remote workers like yourself. May I know your nationality and which country you'd like to apply from?
- (CLIENT) Hello, I'm interested in the DTV visa for Thailand. I work remotely as a software developer for a US company.

AI REPLY:
etc

**INTERMISSION:**

Move the prompt into your database of choice. This prompt will now get updated and improved.

### CURSOR PROMPT 3:

Refactor the script so that it reads the prompt from [database using API KEY]. 

**INTERMISSION:**

Try manually updating the prompt in your database - for example, tell it to send lots of emojis 😀😃😄😁😆🥹😅😂🤣 - then try running the script to see if the AI is properly using the updated live prompt in your database.

### BROWSER PROMPT 2:

(Switch over to Claude broswer, paste in the originally generated AI chatbot prompt, then copy this prompt back into Cursor)

Design and generate an AI chatbot prompt editor prompt. The prompt will take in (1) an existing prompt, (2) client sequence, (3) chat history, (4) real consultant reply, and (5) predicted AI reply. The editor prompt will understand the differences between the real consultant reply and the predicted AI reply, infer the logic and stylistic issues in the AI chatbot prompt, and update the AI chatbot prompt with surgical precision to change specific lines of logic. The editor prompt will return the updated AI chatbot prompt in json format like {"prompt": "new updated prompt"}

### CURSOR PROMPT 4:

[Copy the above generated editor prompt here]

This is an AI chatbot editor prompt. The prompt will take in (1) an existing prompt, (2) client sequence, (3) chat history, (4) real consultant reply, and (5) predicted AI reply. The editor prompt will understand the differences between the real consultant reply and the predicted AI reply, and then update the prompt in json format like {"prompt": "new updated prompt"}. 

Update the script so it uses the editor prompt, run it across samples inputs from `conversations.json`, then set and update the database prompt, then use the new database prompt to generate AI replies.

**INTERMISSION:**

Try testing it and seeing how it works.

### CURSOR PROMPT 5:

Update the Flask server to have the following endpoints:

#### `POST /generate-reply`

Generate an AI response based on conversation context.

**Request:**

```json
{
  "clientSequence": "I'm American and currently in Bali. Can I apply from Indonesia?",
  "chatHistory": [
    { "role": "consultant", "message": "Hi there! Thank you for reaching out. The DTV is perfect for remote workers like yourself. May I know your nationality and which country you'd like to apply from?" },
    { "role": "client", "message": "Hello, I'm interested in the DTV visa for Thailand. I work remotely as a software developer for a US company." }
  ]
}
```

**Response:**

```json
{
  "aiReply": "Great news! As a US citizen, you can apply for the DTV from the Thai Embassy in Jakarta, Indonesia. Processing typically takes 5-7 business days. Would you like me to walk you through the required documents?"
}
```

---

#### `POST /improve-ai`

Auto-improve the AI prompt by comparing predicted vs actual consultant reply.

**Request:**

```json
{
  "clientSequence": "I'm American and currently in Bali. Can I apply from Indonesia?",
  "chatHistory": [...],
  "consultantReply": "Yes, absolutely! You can apply at the Thai Embassy in Jakarta. I'd recommend scheduling an appointment soon as slots fill up quickly."
}
```

**Response:**

```json
{
  "predictedReply": "Great news! As a US citizen, you can apply...",
  "updatedPrompt": "You are a visa consultant specializing in Thai DTV visas..."
}
```

---

#### `POST /improve-ai-manually`

Manually update the AI prompt with specific instructions.

**Request:**

```json
{
  "instructions": "Be more concise. Always mention appointment booking proactively."
}
```

**Response:**

```json
{
  "updatedPrompt": "You are a visa consultant specializing in Thai DTV visas..."
}
```

**INTERMISSION:**

Test the endpoints hosted publicly on Render/Railway and now you're ready to build from here - time to have fun!

## 📦 What We Expect

Submit a **working, testable AI assistant**, not just a concept, presentation, or collection of prompts.

Your project should demonstrate the complete workflow described above:

1. **Generate responses** — Accept customer messages and conversation history, then return a relevant response through `POST /generate-reply`.
2. **Store and retrieve the prompt** — Keep the active assistant prompt in a database and use it when generating responses.
3. **Improve from examples** — Compare a generated response with the actual consultant response, update the prompt, and save the change through `POST /improve-ai`.
4. **Accept manual improvements** — Update the prompt from reviewer instructions through `POST /improve-ai-manually`.

For this assignment, the self-learning workflow refers to **updating the assistant’s prompt**, not training a new model.

### Required Deliverables

- **GitHub repository** containing your source code and dependency information.
- **Hosted server URL** where we can test the application.
- **Example cURL commands** for all three endpoints, including sample requests and expected response formats.
- **README** explaining setup, configuration, system structure, and how the improvement workflow operates.
- **Before-and-after examples** showing the original response, the prompt change, and the resulting response. Explain whether the change improved the result.
- **Brief contribution summary** describing your key decisions, use of AI tools, known limitations, and anything unfinished.

Keep API keys and credentials out of your repository. Provide an `.env.example` with placeholder values instead.

### What Matters Most

We want to see **a functioning workflow, clear technical reasoning, and evidence that you tested your work**. Explain your contribution beyond following the provided prompts.

Additional features are optional. Prioritize making the required functionality reliable and understandable before adding extras.

## 🤖 AI Usage and Prompt Documentation

You are welcome to use AI tools. If you do, include an **AI usage log** so we can understand your process and contribution.

Please include:

- **Tools used** — Which AI tools or models you used and what they helped with.
- **Key prompts and follow-ups** — The prompts that meaningfully shaped your planning, implementation, debugging, or testing, together with relevant AI responses.
- **Your contribution** — What you accepted, modified, or rejected, and how you checked the results.

You may submit an exported chat history, a Markdown/text file, or screenshots. A complete conversation export is not required; selected exchanges with enough context are sufficient.

Add the documentation to your repository as `AI_USAGE.md` or include it with your submission email. Include the assistant’s final application prompts in the project itself.

**Remove API keys, credentials, personal information, and unrelated conversations before sharing.** If you did not use AI tools, state that briefly.

We assess how thoughtfully you use and verify AI assistance—not the number or length of your prompts.

## 🧪 How to Submit

1. Work from anywhere, by yourself, do anything you like
2. When you're done:
   - Email your (i) GitHub project link, (ii) hosted server URL, and (iii) example cURL commands to test your server to **bobalabth@gmail.com**.
   - Use the subject line: **BOBALAB Technical Assessment — [Your Full Name]**.

## ⏰ Submission Deadline

**28 October 2026, 11:59 p.m. — Bangkok time (ICT / UTC+7)**

The one-hour reference earlier in the assignment is a target for an initial working prototype, not the final submission deadline.

Submit all required links and materials by the deadline, and ensure reviewers have access to your repository and hosted application.

**Submit to:** [Insert BOBALAB submission email or form link]

## 🎨 Go Beyond a Working Prototype

A working application is the starting point. What makes your submission stand out is how you improve it, test your decisions, and make it useful for others.

Show us your contribution beyond the generated code:

- **Identify weaknesses** — Where does the assistant give inaccurate, inconsistent, or unhelpful responses?
- **Make deliberate improvements** — Explain what you changed, why it matters, and what trade-offs you considered.
- **Test the results** — Use examples to demonstrate whether your changes actually improved the system.
- **Build for others** — Keep your code understandable, document the setup, and consider how another lab member would maintain it.

Some examples of improvements include:

- Deployment to GCP or AWS using a Dockerized infrastructure, replacing Railway
- A Next.js–based chat interface to visualize conversations and integrate AI workflows
- Diff visualization to surface self-learning edits and model updates

These are examples, not a checklist. Choose improvements that address a real limitation rather than adding complexity for its own sake.

At BOBALAB, we’re looking for founding members who can take ownership of a problem, explain their reasoning, and build tools the team can continue developing. Be ambitious, but be honest about what works, what remains unfinished, and what you would do next.

Good luck and have fun!

— Team BOBALAB 🚀
