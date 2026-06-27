from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    groq_api_key: str = ""

    llm_model: str = "llama-3.3-70b-versatile"
    stt_model: str = "whisper-large-v3-turbo"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    default_language: str = "en"
    max_followups_per_question: int = 2

    questions_path: str = str(BASE_DIR / "data" / "questions.json")
    embeddings_cache_path: str = str(BASE_DIR / "data" / "embeddings_cache.json")

    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "de": "German",
}

TTS_VOICES = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "de": "de-DE-KatjaNeural",
}
TTS_LANGS = {
    "en": "en",
    "hi": "hi",
    "de": "de",
}
