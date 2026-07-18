"""Tests for app.services.transcription (VHIRE-2x / interview audio ->
text via Whisper). Uses a fake OpenAI client rather than a live API call.
"""

from types import SimpleNamespace

import pytest

from app.services import transcription


class _FakeTranscriptions:
    def __init__(self, text: str):
        self.calls: list[dict] = []
        self._text = text

    async def create(self, *, file, model):
        self.calls.append({"file": file, "model": model})
        return SimpleNamespace(text=self._text)


class _FakeOpenAIClient:
    def __init__(self, text: str):
        self.audio = SimpleNamespace(transcriptions=_FakeTranscriptions(text))


@pytest.fixture
def fake_client(monkeypatch) -> _FakeOpenAIClient:
    client = _FakeOpenAIClient("hello from the interview")
    transcription.get_openai_client.cache_clear()
    monkeypatch.setattr(transcription, "get_openai_client", lambda: client)
    return client


async def test_transcribe_audio_returns_the_transcribed_text(fake_client):
    result = await transcription.transcribe_audio(b"audio bytes", "interview.mp3")

    assert result == "hello from the interview"
    call = fake_client.audio.transcriptions.calls[0]
    assert call["file"] == ("interview.mp3", b"audio bytes")
    assert call["model"] == transcription.get_settings().stt_model
