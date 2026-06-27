import asyncio
import base64
import io
import threading

from .config import get_settings, TTS_VOICES, TTS_LANGS


def _run_async(coro):
    box = {}

    def runner():
        loop = asyncio.new_event_loop()
        try:
            box["value"] = loop.run_until_complete(coro)
        except Exception as exc:
            box["error"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


class SpeechToText:
    def __init__(self, client):
        self.settings = get_settings()
        self.client = client

    def transcribe(self, audio_bytes: bytes, filename: str, language: str) -> str:
        resp = self.client.audio.transcriptions.create(
            model=self.settings.stt_model,
            file=(filename, audio_bytes),
            language=language,
        )
        return resp.text.strip()


class TextToSpeech:
    def __init__(self):
        self.settings = get_settings()

    def _voice_for(self, language: str) -> str:
        return TTS_VOICES.get(language, TTS_VOICES["en"])

    def _lang_for(self, language: str) -> str:
        return TTS_LANGS.get(language, "en")

    async def _edge(self, text: str, voice: str) -> bytes:
        import edge_tts

        audio = bytearray()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        return bytes(audio)

    def _gtts(self, text: str, lang: str) -> bytes:
        from gtts import gTTS

        buffer = io.BytesIO()
        gTTS(text=text, lang=lang).write_to_fp(buffer)
        return buffer.getvalue()

    def synthesize_b64(self, text: str, language: str = "en") -> str:
        if not text.strip():
            return ""
        try:
            audio = _run_async(self._edge(text, self._voice_for(language)))
            if not audio:
                raise RuntimeError("empty audio")
        except Exception:
            audio = self._gtts(text, self._lang_for(language))
        return base64.b64encode(audio).decode("utf-8")