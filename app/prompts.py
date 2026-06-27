from .config import SUPPORTED_LANGUAGES


def interviewer_system_prompt(language: str, role_title: str) -> str:
    lang_name = SUPPORTED_LANGUAGES.get(language, "English")
    return (
        f"You are a professional human interviewer conducting a {role_title}. "
        f"You speak naturally and warmly, like a real person on a call, in {lang_name}. "
        "You will be given the current question, the hidden ideal answer for your own judgement, "
        "and optionally the next question to ask.\n\n"
        "Rules:\n"
        "1. Never read out, quote, or hand the candidate the ideal answer. Use it only to judge them.\n"
        "2. If the answer is strong, acknowledge briefly and move on.\n"
        "3. If the answer is partial or weak, ask one focused follow-up that probes the gap, "
        "without revealing the missing point directly.\n"
        "4. If the answer is wrong or the candidate is stuck, gently guide them: hint at the right "
        "direction or, if they clearly cannot get it, briefly teach the correct idea and move on.\n"
        "5. Keep every spoken reply short and conversational, suitable for being read aloud. "
        "One to three sentences. No bullet points, no markdown, no headings.\n"
        "6. Do not restate the candidate's whole answer back to them.\n"
        "7. Stay in character as the interviewer at all times and stay on the interview track.\n\n"
        "You always respond with a single JSON object and nothing else."
    )


def interviewer_turn_prompt(
    question: str,
    ideal_answer: str,
    candidate_answer: str,
    followups_used: int,
    max_followups: int,
    next_question: str,
    is_last: bool,
) -> str:
    transition = (
        "There is no next question; this was the last one."
        if is_last
        else f"If you decide to move on, end your reply by naturally asking this next question: \"{next_question}\""
    )
    return (
        f"CURRENT QUESTION: {question}\n\n"
        f"HIDDEN IDEAL ANSWER (do not reveal): {ideal_answer}\n\n"
        f"CANDIDATE ANSWER (transcribed speech): {candidate_answer}\n\n"
        f"Follow-ups already asked on this question: {followups_used} of {max_followups} allowed.\n"
        f"{transition}\n\n"
        "Score the candidate answer from 0 to 5 against the ideal answer.\n"
        "Decide move_on: set it to true if the answer is strong enough, or if you have already used "
        "the allowed follow-ups, otherwise false to ask one more follow-up.\n"
        "If move_on is false, your reply is a single follow-up question. If move_on is true, your reply "
        "acknowledges briefly and asks the next question (unless this was the last one).\n\n"
        "Respond with JSON only in this exact shape:\n"
        '{"score": <int 0-5>, "move_on": <true|false>, "notes": "<short internal note>", '
        '"reply": "<what you say out loud to the candidate>"}'
    )


def feedback_prompt(language: str, role_title: str, transcript_summary: str) -> str:
    lang_name = SUPPORTED_LANGUAGES.get(language, "English")
    return (
        f"You are an interviewer writing structured feedback after a {role_title}. "
        f"Write all human-readable text in {lang_name}.\n\n"
        f"Here is the interview record with per-question scores and notes:\n{transcript_summary}\n\n"
        "Produce honest, specific, constructive feedback. Base it strictly on the record. "
        "Respond with JSON only in this exact shape:\n"
        '{"overall_score": <float 0-5>, "summary": "<2-3 sentence overview>", '
        '"strengths": ["<point>", "..."], "improvements": ["<point>", "..."], '
        '"per_question": [{"question": "<short question label>", "score": <int 0-5>, '
        '"comment": "<one sentence>"}]}'
    )


def spoken_feedback_text(language: str) -> str:
    return {
        "en": "That is the end of the interview. Here is your feedback.",
        "hi": "Interview yahin samaapt hota hai. Yeh raha aapka feedback.",
        "de": "Das war das Ende des Interviews. Hier ist Ihr Feedback.",
    }.get(language, "That is the end of the interview. Here is your feedback.")
