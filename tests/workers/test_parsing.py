"""Tests for app.workers.tasks.parsing (VHIRE-2x / E6): the parse ->
parsed/parse_failed state machine (I6) and the embed_resume enqueue.
Tests `_parse_resume` (the async task body) directly rather than the
Celery-wrapped task, mirroring tests/workers/test_base.py's approach -
fakes for the DB session and stubs for storage/extraction/Celery rather
than live Postgres/S3/an LLM.
"""

import uuid
from contextlib import asynccontextmanager

import pytest

from app.models.enums import ResumeStatus
from app.models.resume import Resume
from app.workers.tasks import parsing


class _FakeSession:
    def __init__(self, resume: Resume | None):
        self._resume = resume
        self.commit_calls = 0
        self.flush_calls = 0

    async def get(self, model, obj_id):
        return self._resume

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


def _fake_org_scoped_session(session: _FakeSession):
    @asynccontextmanager
    async def _factory(organization_id):
        yield session

    return _factory


def _resume(**overrides) -> Resume:
    defaults = dict(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        file_object_key="org/resume/file.pdf",
        status=ResumeStatus.uploaded,
    )
    return Resume(**{**defaults, **overrides})


@pytest.fixture
def sent_tasks(monkeypatch):
    sent = []
    monkeypatch.setattr(
        parsing.celery_app, "send_task", lambda name, kwargs: sent.append((name, kwargs))
    )
    return sent


async def test_parse_resume_success_sets_parsed_status_and_enqueues_embedding(monkeypatch, sent_tasks):
    resume = _resume()
    session = _FakeSession(resume)
    monkeypatch.setattr(parsing, "org_scoped_session", _fake_org_scoped_session(session))
    monkeypatch.setattr(parsing.storage, "download_object", lambda key: b"raw bytes")
    monkeypatch.setattr(
        parsing.text_extraction, "extract_text", lambda content, filename: "resume text"
    )
    monkeypatch.setattr(parsing, "extract_resume_fields", lambda text: {"skills": ["python"]})

    await parsing._parse_resume(str(resume.id), str(resume.organization_id))

    assert resume.status == ResumeStatus.parsed
    assert resume.parsed_data == {"skills": ["python"]}
    assert resume.parse_error is None
    assert sent_tasks[0][0] == "app.workers.tasks.embedding.embed_resume"
    assert sent_tasks[0][1] == {"resume_id": str(resume.id), "organization_id": str(resume.organization_id)}


async def test_parse_resume_failure_sets_parse_failed_and_does_not_enqueue(monkeypatch, sent_tasks):
    resume = _resume()
    session = _FakeSession(resume)
    monkeypatch.setattr(parsing, "org_scoped_session", _fake_org_scoped_session(session))

    def _raise(key):
        raise RuntimeError("s3 unavailable")

    monkeypatch.setattr(parsing.storage, "download_object", _raise)

    await parsing._parse_resume(str(resume.id), str(resume.organization_id))

    assert resume.status == ResumeStatus.parse_failed
    assert "s3 unavailable" in resume.parse_error
    assert sent_tasks == []


async def test_parse_resume_returns_quietly_when_resume_missing(monkeypatch, sent_tasks):
    session = _FakeSession(None)
    monkeypatch.setattr(parsing, "org_scoped_session", _fake_org_scoped_session(session))

    await parsing._parse_resume(str(uuid.uuid4()), str(uuid.uuid4()))

    assert sent_tasks == []
