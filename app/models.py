from typing import List, Optional
from pydantic import BaseModel


class ReferenceQA(BaseModel):
    id: str
    topic: str
    question: str
    ideal_answer: str
    must_hit: List[str] = []


class TurnRecord(BaseModel):
    question_id: str
    question: str
    candidate_answer: str
    score: int
    notes: str
    was_followup: bool


class StartSessionRequest(BaseModel):
    language: str = "en"
    candidate_name: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    language: str
    reply_text: str
    reply_audio_b64: str
    question_number: int
    total_questions: int
    finished: bool


class RespondResponse(BaseModel):
    session_id: str
    transcript: str
    reply_text: str
    reply_audio_b64: str
    question_number: int
    total_questions: int
    finished: bool


class QuestionFeedback(BaseModel):
    question: str
    score: int
    comment: str


class FeedbackResponse(BaseModel):
    session_id: str
    overall_score: float
    summary: str
    strengths: List[str]
    improvements: List[str]
    per_question: List[QuestionFeedback]
    reply_audio_b64: str
