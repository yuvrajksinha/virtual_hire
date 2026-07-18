"""Tests for app.services.transcripts (VHIRE-2x / transcript+audio
ingestion): the text and audio paths both converging on the same
transcripts.text write and embed_transcript enqueue. Uses a fake
AsyncSession and stubs for transcription/Celery rather than live
Postgres/OpenAI/Redis.
"""

import uuid

import pytest

from app.models.enums import TranscriptSource, TranscriptStatus
from app.models.transcript import Transcript
from app.services import transcription, transcripts
from app.workers import celery_app as celery_app_module


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, existing_transcript: Transcript | None = None):
        self.added: list = []
        self.commit_calls = 0
        self.flush_calls = 0
        self._existing = existing_transcript

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, obj) -> None:
        return None

    async def execute(self, stmt):
        return _FakeResult(self._existing)


@pytest.fixture(autouse=True)
def _stub_celery(monkeypatch):
    sent = []
    monkeypatch.setattr(
        celery_app_module.celery_app, "send_task", lambda name, kwargs: sent.append((name, kwargs))
    )
    return sent


async def test_ingest_transcript_text_creates_new_transcript_and_enqueues_embedding(_stub_celery):
    session = _FakeSession(existing_transcript=None)
    org_id = uuid.uuid4()
    interview_id = uuid.uuid4()

    result = await transcripts.ingest_transcript_text(
        session, organization_id=org_id, interview_id=interview_id, text="hello", language="en"
    )

    assert len(session.added) == 1
    assert result.text == "hello"
    assert result.source == TranscriptSource.platform_provided
    assert result.status == TranscriptStatus.available
    assert _stub_celery[0][0] == "app.workers.tasks.embedding.embed_transcript"


async def test_ingest_transcript_text_reuses_existing_transcript_row(_stub_celery):
    existing = Transcript(id=uuid.uuid4(), organization_id=uuid.uuid4(), interview_id=uuid.uuid4())
    session = _FakeSession(existing_transcript=existing)

    result = await transcripts.ingest_transcript_text(
        session, organization_id=existing.organization_id, interview_id=existing.interview_id, text="updated"
    )

    assert session.added == []
    assert result is existing
    assert existing.text == "updated"


async def test_ingest_transcript_audio_transcribes_then_stores_as_generated_stt(monkeypatch, _stub_celery):
    async def _fake_transcribe(content, filename):
        return "transcribed words"

    monkeypatch.setattr(transcription, "transcribe_audio", _fake_transcribe)
    session = _FakeSession(existing_transcript=None)
    org_id = uuid.uuid4()
    interview_id = uuid.uuid4()

    result = await transcripts.ingest_transcript_audio(
        session,
        organization_id=org_id,
        interview_id=interview_id,
        filename="interview.mp3",
        audio_content=b"audio bytes",
    )

    assert result.text == "transcribed words"
    assert result.source == TranscriptSource.generated_stt
    assert _stub_celery[0][0] == "app.workers.tasks.embedding.embed_transcript"
