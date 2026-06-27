import json
from typing import Dict, List

from .config import get_settings
from . import prompts


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


class Interviewer:
    def __init__(self, client):
        self.settings = get_settings()
        self.client = client

    def _chat(self, system: str, user: str, history: List[Dict[str, str]]) -> dict:
        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": user})
        resp = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        return _extract_json(resp.choices[0].message.content)

    def run_turn(
        self,
        language: str,
        role_title: str,
        question: str,
        ideal_answer: str,
        candidate_answer: str,
        followups_used: int,
        next_question: str,
        is_last: bool,
        history: List[Dict[str, str]],
    ) -> dict:
        system = prompts.interviewer_system_prompt(language, role_title)
        user = prompts.interviewer_turn_prompt(
            question=question,
            ideal_answer=ideal_answer,
            candidate_answer=candidate_answer,
            followups_used=followups_used,
            max_followups=self.settings.max_followups_per_question,
            next_question=next_question,
            is_last=is_last,
        )
        data = self._chat(system, user, history)
        return {
            "score": int(data.get("score", 0)),
            "move_on": bool(data.get("move_on", True)),
            "notes": str(data.get("notes", "")),
            "reply": str(data.get("reply", "")).strip(),
        }

    def open_interview(self, language: str, role_title: str, candidate_name: str, first_question: str) -> str:
        from .config import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(language, "English")
        name_part = f" The candidate's name is {candidate_name}." if candidate_name else ""
        prompt = (
            f"You are starting a {role_title} as a warm, professional human interviewer, speaking {lang_name}."
            f"{name_part} Greet the candidate in one short sentence, then ask this first question naturally "
            f"in {lang_name}: \"{first_question}\". Speak it as you would out loud. "
            "Reply with plain spoken text only, no markdown, two sentences maximum."
        )
        resp = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return resp.choices[0].message.content.strip()

    def build_feedback(self, language: str, role_title: str, transcript_summary: str) -> dict:
        prompt = prompts.feedback_prompt(language, role_title, transcript_summary)
        resp = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return _extract_json(resp.choices[0].message.content)
