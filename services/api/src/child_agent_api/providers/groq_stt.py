"""Speech-to-text via Groq's hosted Whisper API. Used only so the child can
speak instead of type into any of the app's free-text inputs — the
transcribed text goes through the exact same input boxes and content guard
as typed text; this module has no story/session knowledge.
"""

import os

import requests

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"


class GroqSTTError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def transcribe(audio_bytes: bytes, filename: str, mime_type: str) -> str:
    """Convert recorded audio to text. Returns an empty string if nothing
    intelligible was heard (Groq returns that rather than erroring)."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise GroqSTTError("GROQ_API_KEY 未設定")

    response = requests.post(
        GROQ_STT_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": (filename, audio_bytes, mime_type)},
        data={"model": MODEL, "language": "zh", "response_format": "json"},
        timeout=30,
    )
    if response.status_code != 200:
        raise GroqSTTError(f"Groq STT failed ({response.status_code}): {response.text}")

    return response.json().get("text", "").strip()
