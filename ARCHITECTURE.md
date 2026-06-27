# Architecture Note

## 1. System overview

The agent is a five-stage pipeline behind a FastAPI server: speech-to-text → grounding/retrieval → LLM interviewer → text-to-speech → end-of-interview feedback. The browser captures audio with `MediaRecorder` and plays back the synthesised reply. All session state lives in an in-memory `InterviewEngine`. Each external capability (STT, TTS, embeddings, chat) is wrapped in a thin class so a provider can be swapped without touching orchestration. The default stack is fully free: Groq for STT and the chat model, a local `sentence-transformers` model for embeddings, and `edge-tts` for speech (no API key).

The core design choice is the split between **control** and **judgement**. The orchestrator (deterministic Python) owns *which* question is active, how many follow-ups have been spent, and when the interview ends. The LLM owns *what to say*: scoring the answer, deciding whether to probe again, and phrasing a natural reply. Keeping sequencing out of the model prevents the common failure where an LLM interviewer loses the plot, skips questions, or loops.

## 2. Retrieval design

**Storage.** The reference set is a flat JSON file (`data/questions.json`). Each record is one question with its `topic`, `question`, `ideal_answer`, and a `must_hit` checklist. A question is the natural atomic unit of an interview, so I do **not** sub-chunk it — splitting an ideal answer into fragments would let retrieval surface half a rubric and would weaken the LLM's judgement. One record = one chunk = one rubric.

**Indexing.** On startup the store builds one embedding per question from `topic + question + ideal_answer` using a local multilingual `sentence-transformers` model, and caches the vectors to disk keyed by a hash of the source content and the embedding model. Editing the dataset changes the hash and triggers a transparent rebuild; an unchanged dataset loads instantly. Similarity is plain cosine over the in-memory vectors — with 8–12 questions a vector database adds operational weight for no benefit, and an exact scan is sub-millisecond. Running embeddings locally keeps the whole retrieval path free and offline.

**Matching.** The interview is driven, so the orchestrator already knows the active question by index. Each turn it still queries the store with `active_question + candidate_answer` and grounds on the top match. This is deliberate: anchoring the query on the active question keeps grounding stable through follow-ups, while including the candidate's words means the same store doubles as a semantic matcher if the conversation is ever made free-order or the candidate's phrasing drifts. The retrieval path is exercised on every turn rather than being decorative, and the embedding model is multilingual so a Hindi or German answer still maps to the right English rubric.

**Why this over alternatives.** Stuffing all 10 ideal answers into the prompt every turn is possible at this size but leaks the whole rubric into context, costs tokens, and dilutes the model's focus on the question at hand. Retrieving exactly the active rubric keeps the prompt tight and the judgement sharp, and the approach scales to a much larger bank (hundreds of questions across roles) by switching the cosine scan for a vector index — the interface (`store.retrieve`) does not change.

## 3. Keeping the LLM an interviewer (grounded, not leaky)

Three mechanisms hold the behaviour in place.

**Hidden rubric.** The ideal answer is passed to the model labelled as hidden judgement material, and the system prompt forbids reading, quoting, or handing it to the candidate. The model uses it to score and to decide what is missing, but is instructed to probe the gap rather than reveal the missing point — e.g. "What happens to writes when you add that index?" instead of stating the trade-off. Only when a candidate is clearly stuck does the prompt allow a brief teach-then-move-on, which is the genuinely useful interviewer behaviour for practice.

**Structured turns.** Every turn the model returns a single JSON object: `score` (0–5 against the rubric), `move_on` (probe again or advance), `notes` (private), and `reply` (the only thing spoken). JSON mode plus a tolerant parser makes the decision machine-readable, so the orchestrator — not the model — enforces the cap of two follow-ups and the transition to the next question. If the model wants to advance, it is also handed the next question text and weaves the transition naturally; if it has spent its follow-ups, the orchestrator advances regardless of what the model returns.

**Clean context.** The model sees a natural conversation history (candidate transcript ↔ spoken reply), not its own prior JSON, so it stays in character and replies stay short and speakable — one to three sentences, no markdown, suitable for TTS. The opening question and every subsequent question are phrased by the model in the target language, so the experience is fully localised while the dataset stays single-language and easy to maintain.

**Feedback.** At the end, a separate call summarises the collected per-question scores and private notes into an overall score, a short narrative, strengths, improvements, and a per-question breakdown — grounded strictly in the recorded turns, not re-derived from scratch.

## 4. Latency

Where the time goes on a turn (rough order, managed APIs over the network):

| Stage | Typical cost | Notes |
|---|---|---|
| STT (Groq Whisper) | 0.3–1.0 s | Groq is fast; scales with clip length |
| Embedding retrieval | 5–30 ms | local model + in-memory cosine, no network |
| LLM turn (Groq Llama) | 0.4–1.2 s | Groq's high token throughput keeps this low |
| TTS (edge-tts) | 0.4–1.2 s | scales with reply length |

So a turn is roughly 1.5–4 seconds, with STT, the LLM, and TTS as the three real costs; retrieval is negligible because the embedding model is local and the scan is tiny. Choosing Groq for the two network-bound model calls is itself a latency decision — its throughput is well above typical hosted endpoints.

**How I would reduce it.**
- **Stream and pipeline.** Stream STT partials while the candidate speaks, stream LLM tokens, and start TTS on the first sentence instead of waiting for the full reply — this overlaps the three slow stages and cuts perceived latency the most.
- **Keep replies short.** Both LLM and TTS time scale with output length; the one-to-three-sentence constraint is a latency lever as much as a UX one.
- **Cheaper/faster models per stage.** A smaller chat model and a low-latency TTS voice trade marginal quality for responsiveness; the per-stage wrappers make this a config change.
- **Cache the constant parts.** Opening lines and feedback intros are fixed per language and can be pre-synthesised; the local embedding model and its disk cache already remove embedding cost from the hot path.
- **Co-locate.** Run the server in the same region as the API endpoints to shave round-trip time, and reuse one HTTP client (already done) to avoid connection setup per call.

The single highest-leverage change is sentence-level streaming into TTS, because it turns a serial STT→LLM→TTS chain into an overlapped one and lets audio start playing while the rest of the reply is still being generated.
