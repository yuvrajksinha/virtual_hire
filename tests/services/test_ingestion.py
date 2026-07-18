"""Tests for app.services.ingestion (VHIRE-13 / E4): candidate dedup (A8),
file upload, and Resume/Application creation + parse enqueue. Uses a fake
AsyncSession and stubs for storage/Celery rather than live Postgres/S3/Redis.
"""

import uuid

import pytest

from app.models.candidate import Candidate
from app.models.enums import ApplicationStatus, EmbeddingStatus, ResumeStatus
from app.services import ingestion, storage
from app.workers import celery_app as celery_app_module


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, *, existing_candidate: Candidate | None = None):
        self.added: list = []
        self.commit_calls = 0
        self.flush_calls = 0
        self._existing_candidate = existing_candidate

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, obj) -> None:
        return None

    async def execute(self, stmt):
        return _FakeResult(self._existing_candidate)


@pytest.fixture(autouse=True)
def _stub_external_calls(monkeypatch):
    uploads = []
    sent_tasks = []

    monkeypatch.setattr(storage, "upload_object", lambda *, key, content: uploads.append((key, content)))
    monkeypatch.setattr(
        celery_app_module.celery_app,
        "send_task",
        lambda name, kwargs: sent_tasks.append((name, kwargs)),
    )
    return {"uploads": uploads, "sent_tasks": sent_tasks}


async def test_submit_resume_creates_new_candidate_when_none_exists(_stub_external_calls):
    session = _FakeSession(existing_candidate=None)
    org_id = uuid.uuid4()
    requisition_id = uuid.uuid4()

    application = await ingestion.submit_resume(
        session,
        organization_id=org_id,
        job_requisition_id=requisition_id,
        candidate_email="candidate@example.test",
        candidate_full_name="Jane Candidate",
        candidate_phone=None,
        filename="resume.pdf",
        file_content=b"pdf-bytes",
    )

    candidates_added = [obj for obj in session.added if isinstance(obj, Candidate)]
    assert len(candidates_added) == 1
    assert application.status == ApplicationStatus.submitted
    assert application.organization_id == org_id
    assert application.job_requisition_id == requisition_id


async def test_submit_resume_reuses_existing_candidate(_stub_external_calls):
    org_id = uuid.uuid4()
    existing = Candidate(
        id=uuid.uuid4(), organization_id=org_id, email="candidate@example.test", full_name="Jane"
    )
    session = _FakeSession(existing_candidate=existing)

    application = await ingestion.submit_resume(
        session,
        organization_id=org_id,
        job_requisition_id=uuid.uuid4(),
        candidate_email="candidate@example.test",
        candidate_full_name="Jane Candidate",
        candidate_phone=None,
        filename="resume.pdf",
        file_content=b"pdf-bytes",
    )

    candidates_added = [obj for obj in session.added if isinstance(obj, Candidate)]
    assert candidates_added == []
    assert application.candidate_id == existing.id


async def test_submit_resume_uploads_file_and_sets_resume_defaults(_stub_external_calls):
    session = _FakeSession()

    await ingestion.submit_resume(
        session,
        organization_id=uuid.uuid4(),
        job_requisition_id=uuid.uuid4(),
        candidate_email="candidate@example.test",
        candidate_full_name="Jane Candidate",
        candidate_phone="555-0100",
        filename="resume.pdf",
        file_content=b"pdf-bytes",
    )

    assert len(_stub_external_calls["uploads"]) == 1
    key, content = _stub_external_calls["uploads"][0]
    assert content == b"pdf-bytes"
    assert key.endswith("resume.pdf")

    resumes_added = [obj for obj in session.added if type(obj).__name__ == "Resume"]
    assert resumes_added[0].status == ResumeStatus.uploaded
    assert resumes_added[0].embedding_status == EmbeddingStatus.not_embedded


async def test_submit_resume_enqueues_parse_resume_task(_stub_external_calls):
    session = _FakeSession()

    application = await ingestion.submit_resume(
        session,
        organization_id=uuid.uuid4(),
        job_requisition_id=uuid.uuid4(),
        candidate_email="candidate@example.test",
        candidate_full_name="Jane Candidate",
        candidate_phone=None,
        filename="resume.pdf",
        file_content=b"pdf-bytes",
    )

    assert len(_stub_external_calls["sent_tasks"]) == 1
    task_name, kwargs = _stub_external_calls["sent_tasks"][0]
    assert task_name == "app.workers.tasks.parsing.parse_resume"
    assert kwargs["resume_id"] == str(application.resume_id)
