"""ElevenLabs text-to-speech provider.

Interface: text in, audio bytes out. No web-framework or story/session
knowledge here — callers decide what to do with the audio (save it,
stream it, attach it to a scene, etc).
"""

import os

import requests

DEFAULT_VOICE_ID = "r6qgCCGI7RWKXCagm158"  # anna su
API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class TTSError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"ElevenLabs TTS failed ({status_code}): {message}")


def synthesize_speech(
    text: str,
    voice_id: str = DEFAULT_VOICE_ID,
    stability: float = 0.4,
    similarity_boost: float = 0.75,
) -> bytes:
    """Convert text to speech and return the raw mp3 bytes."""
    if not text or not text.strip():
        raise ValueError("text 不可為空")

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise TTSError(500, "ELEVENLABS_API_KEY 未設定")

    response = requests.post(
        API_URL.format(voice_id=voice_id),
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",  # 中文需要這個 model
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise TTSError(response.status_code, response.text)

    return response.content
