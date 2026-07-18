"""Tests for app.workers.tasks.verdicts (RAG-driven Scoring Engine +
Judge, "scorecard logic"): the resume and transcript verdict generation
pipelines, I14's completed-interview gate, and the upsert-in-place
behavior. Tests the async task bodies directly, mirroring
tests/workers/test_parsing.py's approach - fakes/stubs rather than live
Postgres/Qdrant/Voyage/an LLM.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from app.models.application import Application
from app.models.enums import InterviewStatus, VerdictServiceType
from app.models.interview import Interview
from app.models.job_requisition import JobRequisition
from app.models.resume import Resume
from app.models.transcript import Transcript
from app.models.verdict import Verdict
from app.workers.tasks import verdicts


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """Dispatches `execute(select(Model)...)` by the statement's target
    entity class, and `.get(model, id)` by `str(id)` (see
    tests/workers/test_embedding.py's `_FakeSession` for why)."""

    def __init__(self, objects: list | None = None, existing_verdict: Verdict | None = None):
        self.store = {str(obj.id): obj for obj in (objects or [])}
        self.existing_verdict = existing_verdict
        self.added: list = []
        self.commit_calls = 0

    async def get(self, model, obj_id):
        return self.store.get(str(obj_id))

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Verdict:
            return _FakeResult(self.existing_verdict)
        if entity is Transcript:
            for obj in self.store.values():
                if isinstance(obj, Transcript):
                    return _FakeResult(obj)
            return _FakeResult(None)
        raise AssertionError(f"unexpected select target in test: {entity}")

    def add(self, obj) -> None:
        self.added.append(obj)
        self.store[str(getattr(obj, "id", uuid.uuid4()))] = obj

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, obj) -> None:
        return None


def _fake_org_scoped_session(session: _FakeSession):
    @asynccontextmanager
    async def _factory(organization_id):
        yield session

    return _factory


@pytest.fixture(autouse=True)
def _stub_rag_and_judge(monkeypatch):
    search_calls = []
    judge_calls = []

    async def _fake_embed_chunks(texts):
        return [[0.1, 0.2] for _ in texts]

    async def _fake_search(organization_id, query_vector, *, source_type=None, source_id=None, limit=10):
        search_calls.append({"source_type": source_type, "source_id": source_id})
        return []

    def _fake_run_judge(*, deterministic_score, context_chunks, task_description):
        judge_calls.append(
            {
                "deterministic_score": deterministic_score,
                "context_chunks": context_chunks,
                "task_description": task_description,
            }
        )
        return {"verdict_label": "pass", "narrative": "Looks solid."}

    monkeypatch.setattr(verdicts.embeddings, "embed_chunks", _fake_embed_chunks)
    monkeypatch.setattr(verdicts.vector_store, "search", _fake_search)
    monkeypatch.setattr(verdicts.judge_agent, "run_judge", _fake_run_judge)
    return {"search_calls": search_calls, "judge_calls": judge_calls}


def _application(**overrides) -> Application:
    defaults = dict(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        job_requisition_id=uuid.uuid4(),
        resume_id=uuid.uuid4(),
    )
    return Application(**{**defaults, **overrides})


async def test_generate_resume_verdict_creates_a_new_verdict(monkeypatch, _stub_rag_and_judge):
    application = _application()
    resume = Resume(
        id=application.resume_id,
        organization_id=application.organization_id,
        candidate_id=application.candidate_id,
        file_object_key="k",
        parsed_data={"skills": ["python"], "work_history": [{"title": "Engineer"}]},
    )
    requisition = JobRequisition(
        id=application.job_requisition_id,
        organization_id=application.organization_id,
        title="Backend Engineer",
        owner_hr_user_id=uuid.uuid4(),
        scorecard_template={"required_skills": ["python"]},
    )
    session = _FakeSession([application, resume, requisition])
    monkeypatch.setattr(verdicts, "org_scoped_session", _fake_org_scoped_session(session))

    await verdicts._generate_resume_verdict(str(application.id), str(application.organization_id))

    assert len(session.added) == 1
    verdict = session.added[0]
    assert verdict.service_type == VerdictServiceType.resume_analysis
    assert verdict.resume_id == resume.id
    assert verdict.verdict_label.value == "pass"
    assert verdict.deterministic_score["skill_match_ratio"] == 1.0
    assert _stub_rag_and_judge["search_calls"][0]["source_type"] == "resume"


async def test_generate_resume_verdict_overwrites_existing_verdict_in_place(monkeypatch, _stub_rag_and_judge):
    application = _application()
    resume = Resume(
        id=application.resume_id,
        organization_id=application.organization_id,
        candidate_id=application.candidate_id,
        file_object_key="k",
        parsed_data={"skills": ["python"], "work_history": []},
    )
    requisition = JobRequisition(
        id=application.job_requisition_id,
        organization_id=application.organization_id,
        title="Backend Engineer",
        owner_hr_user_id=uuid.uuid4(),
        scorecard_template={},
    )
    existing = Verdict(
        id=uuid.uuid4(),
        organization_id=application.organization_id,
        application_id=application.id,
        service_type=VerdictServiceType.resume_analysis,
        deterministic_score={"old": True},
        verdict_label="fail",
        narrative="old narrative",
        crew_run={},
        generated_at=datetime.now(UTC),
        stale=True,
    )
    session = _FakeSession([application, resume, requisition], existing_verdict=existing)
    monkeypatch.setattr(verdicts, "org_scoped_session", _fake_org_scoped_session(session))

    await verdicts._generate_resume_verdict(str(application.id), str(application.organization_id))

    assert session.added == []
    assert existing.verdict_label.value == "pass"
    assert existing.stale is False


async def test_generate_resume_verdict_skips_when_resume_not_parsed(monkeypatch, _stub_rag_and_judge):
    application = _application()
    resume = Resume(
        id=application.resume_id,
        organization_id=application.organization_id,
        candidate_id=application.candidate_id,
        file_object_key="k",
        parsed_data=None,
    )
    requisition = JobRequisition(
        id=application.job_requisition_id,
        organization_id=application.organization_id,
        title="Backend Engineer",
        owner_hr_user_id=uuid.uuid4(),
        scorecard_template={},
    )
    session = _FakeSession([application, resume, requisition])
    monkeypatch.setattr(verdicts, "org_scoped_session", _fake_org_scoped_session(session))

    await verdicts._generate_resume_verdict(str(application.id), str(application.organization_id))

    assert session.added == []
    assert _stub_rag_and_judge["judge_calls"] == []


async def test_generate_transcript_verdict_rejects_non_completed_interview(monkeypatch, _stub_rag_and_judge):
    interview = Interview(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        application_id=uuid.uuid4(),
        interviewer_hr_user_id=uuid.uuid4(),
        scheduled_at=datetime.now(UTC),
        status=InterviewStatus.scheduled,
    )
    session = _FakeSession([interview])
    monkeypatch.setattr(verdicts, "org_scoped_session", _fake_org_scoped_session(session))

    await verdicts._generate_transcript_verdict(str(interview.id), str(interview.organization_id))

    assert session.added == []
    assert _stub_rag_and_judge["judge_calls"] == []


async def test_generate_transcript_verdict_produces_a_verdict_for_completed_interview(
    monkeypatch, _stub_rag_and_judge
):
    interview = Interview(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        application_id=uuid.uuid4(),
        interviewer_hr_user_id=uuid.uuid4(),
        scheduled_at=datetime.now(UTC),
        status=InterviewStatus.completed,
    )
    transcript = Transcript(
        id=uuid.uuid4(),
        organization_id=interview.organization_id,
        interview_id=interview.id,
        text=" ".join(["word"] * 250),
    )
    session = _FakeSession([interview, transcript])
    monkeypatch.setattr(verdicts, "org_scoped_session", _fake_org_scoped_session(session))

    await verdicts._generate_transcript_verdict(str(interview.id), str(interview.organization_id))

    assert len(session.added) == 1
    verdict = session.added[0]
    assert verdict.service_type == VerdictServiceType.transcript_assignment_review
    assert verdict.interview_id == interview.id
    assert verdict.resume_id is None
    assert _stub_rag_and_judge["search_calls"][0]["source_type"] == "transcript"
