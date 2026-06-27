# Voice Interview Agent

A voice-based mock interview agent. A candidate speaks with it, and it conducts a realistic interview: asking questions from a fixed reference set, listening, asking natural follow-ups, guiding when an answer is wrong, and producing structured feedback at the end. The interviewer is an LLM grounded in a reference question / ideal-answer store so its judgement stays consistent.

Runs on a **fully free stack** — one free API key (Groq), everything else free or local. No paid services.

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
TTS  (edge-tts)  ──►  audio reply  ──►  browser playback
   │
   ▼
Feedback  (LLM over per-turn scores/notes)  ──►  structured report + audio
```

## Stack (all free)

- **Backend:** Python, FastAPI
- **STT:** Groq `whisper-large-v3-turbo` (free tier, multilingual)
- **LLM:** Groq `llama-3.3-70b-versatile` (free tier, JSON mode, very fast)
- **Embeddings / retrieval:** `sentence-transformers` multilingual model, runs locally, cached, cosine similarity in process — no API, no key
- **TTS:** `edge-tts` — free, no API key at all, neural voices for English / Hindi / German
- **Frontend:** static HTML/JS, `MediaRecorder` for capture, base64 MP3 playback

Each external capability is wrapped behind a small class (`app/voice.py`, `app/llm.py`, `app/embeddings.py`), so swapping a provider (e.g. local faster-whisper, Gemini, Piper TTS) means changing one file, not the core logic.

## Requirements

- Python 3.10+
- A free Groq API key — sign up at https://console.groq.com (no credit card), create a key, paste it into `.env`
- A browser with microphone access (Chrome or Edge recommended for `MediaRecorder`)

## Setup

```bash
cp .env.example .env          # then put your free GROQ_API_KEY in .env
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On Windows (PowerShell):

```powershell
copy .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`, pick a language, and click **Start interview**. Hold the orb to answer, release to send.

> First run downloads the sentence-transformers model (~470 MB) once and builds the embedding cache. Subsequent starts are instant.

> Microphone capture needs a secure context. `localhost` counts as secure, so local runs work. Behind a remote host, serve it over HTTPS.

## Updating the reference Q&A

Edit `data/questions.json`. Each entry:

```json
{
  "id": "se_11",
  "topic": "caching",
  "question": "What is a cache, and what are the main invalidation strategies?",
  "ideal_answer": "A strong answer covers ...",
  "must_hit": ["definition", "TTL", "write-through vs write-back", "invalidation is hard"]
}
```

No code changes needed. The store hashes the questions and ideal answers; when the file changes, the embedding cache (`data/embeddings_cache.json`) rebuilds automatically on the next start. Add, edit, remove, or reorder questions freely. The interview walks them in file order.

## Languages

Pick the language in the UI (English, Hindi, German) or set `DEFAULT_LANGUAGE` in `.env`. The language is passed to STT (transcription hint), used to instruct the LLM to ask and converse in that language, and used to pick the `edge-tts` voice. The reference dataset stays in one language (English here); the LLM asks the stored questions naturalised into the target language and evaluates answers regardless of the language spoken. To add a language, add it to `SUPPORTED_LANGUAGES` and a voice to `TTS_VOICES` in `app/config.py`.

## Configuration

All settings live in `.env` (see `.env.example`): the Groq key, models for STT and LLM, the embedding model, `MAX_FOLLOWUPS_PER_QUESTION`, and the dataset path.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Web UI |
| GET | `/api/config` | Languages, role title, question count |
| POST | `/api/session/start` | Create a session, get the opening question (text + audio) |
| POST | `/api/session/{id}/respond` | Upload an answer (audio), get transcript + interviewer reply (text + audio) |
| POST | `/api/session/{id}/feedback` | End the interview, get structured feedback |

## Project layout

```
app/
  main.py        FastAPI routes and wiring
  config.py      settings (pydantic-settings)
  models.py      request/response/domain schemas
  embeddings.py  local sentence-transformers embedder
  retrieval.py   embedding store + cosine retrieval + cache
  llm.py         interviewer turns + feedback (JSON-mode chat)
  voice.py       Groq STT + edge-tts TTS wrappers
  interview.py   session state machine / orchestration
  prompts.py     prompt templates
data/
  questions.json reference Q&A dataset
static/          web UI (index.html, app.js, styles.css)
```

## Notes

- Sessions are kept in memory; restarting the server clears them. A real deployment would use Redis or a database.
- The agent never reads the ideal answer aloud; it is used only for the LLM's hidden judgement. See `ARCHITECTURE.md`.
