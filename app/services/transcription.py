"""Speech-to-text for interview audio recordings without a
platform-provided transcript. OpenAI's Whisper API is a swappable
default (per docs/07-technical-stack.md's still-open STT vendor
question), not a final vendor decision - see vector.md.

VHIRE-2x (transcript/audio RAG pipeline extension).
"""

from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import get_settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """Return the process-wide AsyncOpenAI client, constructed once and cached."""
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key or None)


async def transcribe_audio(content: bytes, filename: str) -> str:
    """Transcribe an interview audio recording to plain text via Whisper.

    Raises:
        Whatever the underlying OpenAI SDK raises on failure (network,
        auth, unsupported format) - the caller is responsible for
        deciding how to handle it.
    """
    settings = get_settings()
    client = get_openai_client()
    transcription = await client.audio.transcriptions.create(
        file=(filename, content),
        model=settings.stt_model,
    )
    return transcription.text
