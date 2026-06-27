from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq

from .config import get_settings, SUPPORTED_LANGUAGES, BASE_DIR
from .models import (
    StartSessionRequest,
    StartSessionResponse,
    RespondResponse,
    FeedbackResponse,
    QuestionFeedback,
)
from .retrieval import ReferenceStore
from .embeddings import LocalEmbedder
from .llm import Interviewer
from .voice import SpeechToText, TextToSpeech
from .interview import InterviewEngine


settings = get_settings()
app = FastAPI(title="Voice Interview Agent")

_client = Groq(api_key=settings.groq_api_key)
_embedder = LocalEmbedder()
_store = ReferenceStore(_embedder)
_engine = InterviewEngine(
    store=_store,
    interviewer=Interviewer(_client),
    stt=SpeechToText(_client),
    tts=TextToSpeech(),
)

STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/config")
def config() -> JSONResponse:
    return JSONResponse(
        {
            "languages": SUPPORTED_LANGUAGES,
            "default_language": settings.default_language,
            "role_title": _engine.role_title,
            "total_questions": _store.count(),
        }
    )


@app.post("/api/session/start", response_model=StartSessionResponse)
def start_session(body: StartSessionRequest) -> StartSessionResponse:
    if body.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported language")
    session = _engine.start(body.language, body.candidate_name or "")
    reply_text = _engine.opening_reply(session)
    audio = _engine.speak(reply_text, session.language)
    return StartSessionResponse(
        session_id=session.session_id,
        language=session.language,
        reply_text=reply_text,
        reply_audio_b64=audio,
        question_number=1,
        total_questions=_store.count(),
        finished=False,
    )


@app.post("/api/session/{session_id}/respond", response_model=RespondResponse)
def respond(session_id: str, audio: UploadFile = File(...)) -> RespondResponse:
    try:
        session = _engine.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.finished:
        raise HTTPException(status_code=400, detail="Interview already finished")

    audio_bytes = audio.file.read()
    transcript = _engine.transcribe(audio_bytes, audio.filename or "answer.webm", session.language)

    reply_text = _engine.process_answer(session, transcript)
    audio_b64 = _engine.speak(reply_text, session.language)

    return RespondResponse(
        session_id=session.session_id,
        transcript=transcript,
        reply_text=reply_text,
        reply_audio_b64=audio_b64,
        question_number=_engine.question_number(session),
        total_questions=_store.count(),
        finished=session.finished,
    )


@app.post("/api/session/{session_id}/feedback", response_model=FeedbackResponse)
def feedback(session_id: str) -> FeedbackResponse:
    try:
        session = _engine.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    data = _engine.build_feedback(session)
    intro = _engine.feedback_intro(session.language)
    audio_b64 = _engine.speak(intro + " " + data.get("summary", ""), session.language)

    per_question = [
        QuestionFeedback(
            question=item.get("question", ""),
            score=int(item.get("score", 0)),
            comment=item.get("comment", ""),
        )
        for item in data.get("per_question", [])
    ]

    return FeedbackResponse(
        session_id=session.session_id,
        overall_score=float(data.get("overall_score", 0.0)),
        summary=data.get("summary", ""),
        strengths=data.get("strengths", []),
        improvements=data.get("improvements", []),
        per_question=per_question,
        reply_audio_b64=audio_b64,
    )
