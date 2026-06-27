import uuid
from dataclasses import dataclass, field
from typing import Dict, List

from .config import get_settings
from .models import TurnRecord
from .retrieval import ReferenceStore
from .llm import Interviewer
from .voice import SpeechToText, TextToSpeech
from . import prompts


@dataclass
class Session:
    session_id: str
    language: str
    candidate_name: str
    current_index: int = 0
    followups_used: int = 0
    finished: bool = False
    history: List[Dict[str, str]] = field(default_factory=list)
    turns: List[TurnRecord] = field(default_factory=list)


class InterviewEngine:
    def __init__(self, store: ReferenceStore, interviewer: Interviewer, stt: SpeechToText, tts: TextToSpeech):
        self.settings = get_settings()
        self.store = store
        self.interviewer = interviewer
        self.stt = stt
        self.tts = tts
        self.sessions: Dict[str, Session] = {}

    @property
    def role_title(self) -> str:
        return self.store.title or "software engineer screening"

    def start(self, language: str, candidate_name: str) -> Session:
        session = Session(
            session_id=uuid.uuid4().hex,
            language=language,
            candidate_name=candidate_name or "",
        )
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        return self.sessions[session_id]

    def opening_reply(self, session: Session) -> str:
        first_question = self.store.get_by_index(0)
        return self.interviewer.open_interview(
            language=session.language,
            role_title=self.role_title,
            candidate_name=session.candidate_name,
            first_question=first_question.question,
        )

    def transcribe(self, audio_bytes: bytes, filename: str, language: str) -> str:
        return self.stt.transcribe(audio_bytes, filename, language)

    def speak(self, text: str, language: str = "en") -> str:
        return self.tts.synthesize_b64(text, language)

    def process_answer(self, session: Session, candidate_answer: str) -> str:
        question = self.store.get_by_index(session.current_index)
        grounded = self.store.retrieve(f"{question.question} {candidate_answer}", k=1)
        reference = grounded[0][0] if grounded else question

        next_index = session.current_index + 1
        is_last = next_index >= self.store.count()
        next_question = "" if is_last else self.store.get_by_index(next_index).question

        result = self.interviewer.run_turn(
            language=session.language,
            role_title=self.role_title,
            question=question.question,
            ideal_answer=reference.ideal_answer,
            candidate_answer=candidate_answer,
            followups_used=session.followups_used,
            next_question=next_question,
            is_last=is_last,
            history=session.history,
        )

        session.turns.append(
            TurnRecord(
                question_id=question.id,
                question=question.question,
                candidate_answer=candidate_answer,
                score=result["score"],
                notes=result["notes"],
                was_followup=session.followups_used > 0,
            )
        )

        session.history.append({"role": "user", "content": candidate_answer})
        session.history.append({"role": "assistant", "content": result["reply"]})

        force_advance = session.followups_used >= self.settings.max_followups_per_question
        if result["move_on"] or force_advance:
            if is_last:
                session.finished = True
            else:
                session.current_index = next_index
                session.followups_used = 0
        else:
            session.followups_used += 1

        return result["reply"]

    def question_number(self, session: Session) -> int:
        if session.finished:
            return self.store.count()
        return session.current_index + 1

    def build_feedback(self, session: Session) -> dict:
        lines = []
        for turn in session.turns:
            tag = "follow-up" if turn.was_followup else "main"
            lines.append(
                f"[{tag}] Q: {turn.question}\nCandidate: {turn.candidate_answer}\n"
                f"Score: {turn.score}/5\nInterviewer note: {turn.notes}"
            )
        summary = "\n\n".join(lines) if lines else "No answers were recorded."
        return self.interviewer.build_feedback(session.language, self.role_title, summary)

    def feedback_intro(self, language: str) -> str:
        return prompts.spoken_feedback_text(language)
