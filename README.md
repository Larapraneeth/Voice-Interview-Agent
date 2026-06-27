# Voice Interview Agent

A voice-based mock interview agent. A candidate speaks with it, and it conducts a realistic interview — asking questions from a fixed reference set, listening, asking natural follow-ups, guiding when an answer is wrong, and producing structured feedback at the end. The interviewer is an LLM **grounded** in a reference question / ideal-answer store, so its judgement stays consistent while it still behaves like a real, adaptive interviewer.

Runs on a **fully free stack** — one free API key (Groq), everything else free or local. No paid services, no credit card.

---


---

## Features

- 🎙️ **Real voice in / voice out** — speech-to-text on the way in, text-to-speech on the way out.
- 📚 **Grounded judgement** — every turn is anchored to a reference question and an ideal answer retrieved from a local embedding store, so scoring is consistent.
- 🧠 **Behaves like an interviewer** — asks the next question, probes weak answers with one focused follow-up, gently guides wrong answers, and never reads the ideal answer aloud.
- 🌍 **Multilingual** — English, Hindi, and German out of the box.
- 📝 **Easy-to-update Q&A** — questions live in a single JSON file; add, edit, remove, or reorder them with no code changes.
- 📊 **Structured feedback** — overall score, summary, strengths, areas to improve, and a per-question breakdown.

---

## Pipeline

```
mic (browser)
   │  WebM audio
   ▼
STT  (Groq Whisper)  ──►  transcript
   │
   ▼
Grounding  (local embedding store)  ──►  reference Q + ideal answer for the active question
   │
   ▼
LLM interviewer  (Groq Llama, JSON out)  ──►  score + follow-up/advance + spoken reply
   │
   ▼
TTS  (edge-tts, gTTS fallback)  ──►  audio reply  ──►  browser playback
   │
   ▼
Feedback  (LLM over per-turn scores/notes)  ──►  structured report + audio
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the reasoning behind retrieval design, grounding, and latency.

---

## Tech stack (all free)

| Stage | Provider | Notes |
|---|---|---|
| Backend | Python + FastAPI | |
| Speech-to-text | Groq `whisper-large-v3-turbo` | free tier, multilingual |
| LLM interviewer | Groq `llama-3.3-70b-versatile` | free tier, JSON mode, fast |
| Embeddings / retrieval | `sentence-transformers` (multilingual MiniLM) | runs locally, no key |
| Text-to-speech | `edge-tts` → `gTTS` fallback | no API key; gTTS used if edge-tts is unavailable |
| Frontend | HTML / JS, `MediaRecorder` | base64 MP3 playback |

Each external capability sits behind a small wrapper class (`app/voice.py`, `app/llm.py`, `app/embeddings.py`), so swapping a provider means changing one file, not the core logic.

---

## Prerequisites

- Python 3.10+
- A free **Groq API key** — sign up at https://console.groq.com (no card), go to **API Keys → Create API Key**, copy the `gsk_...` key.
- A browser with microphone access (Chrome or Edge recommended for `MediaRecorder`).

---

## Setup

```powershell
# from the project folder
copy .env.example .env
```

Open `.env` and paste your real key:

```
GROQ_API_KEY=gsk_your_real_key_here
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the server (use `python -m` so it works regardless of PATH):

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser.

> ⚠️ Open `localhost`, **not** `0.0.0.0`. The server *listens* on `0.0.0.0` (all interfaces), but browsers can't navigate to that literal address.

> First launch downloads the sentence-transformers model (~470 MB) once and builds the embedding cache. Later starts are instant.

---

## Usage

1. Pick a language and (optionally) enter your name.
2. Click **Start interview** — the agent greets you and asks the first question by voice.
3. **Hold the orb** to answer, release to send. Your speech is transcribed and the agent replies.
4. The agent asks follow-ups on weak answers and moves on when satisfied.
5. Click **End & get feedback** (or finish all questions) to see your structured report.

---

## Updating the reference Q&A

Edit [`data/questions.json`](data/questions.json). Each entry:

```json
{
  "id": "se_11",
  "topic": "caching",
  "question": "What is a cache, and what are the main invalidation strategies?",
  "ideal_answer": "A strong answer covers ...",
  "must_hit": ["definition", "TTL", "write-through vs write-back", "invalidation is hard"]
}
```

No code changes needed. The store hashes the questions and ideal answers; when the file changes, the embedding cache rebuilds automatically on the next start. Questions are asked in file order.

---

## Languages

Pick the language in the UI (English, Hindi, German) or set `DEFAULT_LANGUAGE` in `.env`. The language is passed to STT (transcription hint), used to instruct the LLM to ask and converse in that language, and used to pick the TTS voice. The dataset stays in one language (English here); the LLM asks the stored questions naturalised into the target language and evaluates answers regardless of the language spoken.

To add a language, add it to `SUPPORTED_LANGUAGES`, `TTS_VOICES`, and `TTS_LANGS` in `app/config.py`.

---

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | your free Groq key |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | interviewer model |
| `STT_MODEL` | `whisper-large-v3-turbo` | transcription model |
| `EMBEDDING_MODEL` | multilingual MiniLM | local embedding model |
| `DEFAULT_LANGUAGE` | `en` | starting language |
| `MAX_FOLLOWUPS_PER_QUESTION` | `2` | follow-up cap per question |

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Web UI |
| GET | `/api/config` | Languages, role title, question count |
| POST | `/api/session/start` | Create a session, get the opening question (text + audio) |
| POST | `/api/session/{id}/respond` | Upload an answer (audio), get transcript + interviewer reply (text + audio) |
| POST | `/api/session/{id}/feedback` | End the interview, get structured feedback |

---

## Project structure

```
app/
  main.py        FastAPI routes and wiring
  config.py      settings (pydantic-settings)
  models.py      request/response/domain schemas
  embeddings.py  local sentence-transformers embedder
  retrieval.py   embedding store + cosine retrieval + cache
  llm.py         interviewer turns + feedback (JSON-mode chat)
  voice.py       Groq STT + edge-tts/gTTS wrappers
  interview.py   session state machine / orchestration
  prompts.py     prompt templates
data/
  questions.json reference Q&A dataset
static/          web UI (index.html, app.js, styles.css)
ARCHITECTURE.md  design note (retrieval, grounding, latency)
```

---

## Troubleshooting

**`uvicorn` is not recognized**
Its script isn't on PATH. Always run with `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.

**`AttributeError: 'MessageFactory' object has no attribute 'GetPrototype'`**
A broken system TensorFlow install gets pulled in by `transformers`. The app forces it off in `app/embeddings.py` (`USE_TF=0`). If you still see it, set it manually before running: `$env:USE_TF=0`.

**`ERR_ADDRESS_INVALID` for `http://0.0.0.0:8000`**
Open **http://localhost:8000** instead. `0.0.0.0` is a listen address, not a browse address.

**edge-tts `WSServerHandshakeError: 403`**
Microsoft's free TTS endpoint occasionally rejects requests. The app automatically falls back to gTTS, so the interview continues. No action needed.

**Microphone blocked**
`MediaRecorder` needs a secure context. `localhost` / `127.0.0.1` count as secure. Behind a remote host, serve over HTTPS.

---

## Notes & limitations

- Sessions are kept in memory; restarting the server clears them. A production version would use Redis or a database.
- The agent never reads the ideal answer aloud — it's used only for the LLM's hidden judgement.
- `.env` holds your secret key and is git-ignored. Never commit it.

---

## License

Add a license of your choice (e.g. MIT) before publishing.
