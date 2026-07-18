"""Verdict generation: the RAG-driven "scorecard logic" - Scoring Engine
first, then a RAG retrieval step over the candidate's own embedded
content, then the Judge agent, then a `verdicts` row (I12's ordering
guarantee). `generate_resume_verdict` and `generate_transcript_verdict`
share `_upsert_verdict`; see vector.md for the full pipeline.

VHIRE-2x.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.crew.agents import judge as judge_agent
from app.models.application import Application
from app.models.enums import InterviewStatus, VerdictLabel, VerdictServiceType
from app.models.interview import Interview
from app.models.job_requisition import JobRequisition
from app.models.resume import Resume
from app.models.transcript import Transcript
from app.models.verdict import Verdict
from app.services import embeddings, vector_store
from app.services.scoring import resume_fit, transcript_review
from app.workers.base import OrgScopedTask, org_scoped_session, run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _requisition_requirements(requisition: JobRequisition) -> dict:
    """Read an optional `required_skills` list out of a requisition's
    `scorecard_template` JSONB - the closest existing field to a
    structured "requirements" input, since `job_requisitions` has no
    dedicated requirements column (see docs/05-data-model.md).
    """
    template = requisition.scorecard_template or {}
    return {"required_skills": template.get("required_skills", [])}


async def _upsert_verdict(
    session,
    *,
    organization_id: uuid.UUID,
    application_id: uuid.UUID,
    service_type: VerdictServiceType,
    resume_id: uuid.UUID | None,
    interview_id: uuid.UUID | None,
    deterministic_score: dict,
    verdict_label: VerdictLabel,
    narrative: str,
    crew_run: dict,
) -> Verdict:
    """Create or overwrite-in-place the (application_id, service_type) Verdict."""
    result = await session.execute(
        select(Verdict).where(Verdict.application_id == application_id, Verdict.service_type == service_type)
    )
    verdict = result.scalar_one_or_none()

    generated_at = datetime.now(UTC)
    if verdict is None:
        verdict = Verdict(
            organization_id=organization_id,
            application_id=application_id,
            service_type=service_type,
        )
        session.add(verdict)

    verdict.resume_id = resume_id
    verdict.interview_id = interview_id
    verdict.deterministic_score = deterministic_score
    verdict.verdict_label = verdict_label
    verdict.narrative = narrative
    verdict.crew_run = crew_run
    verdict.generated_at = generated_at
    verdict.stale = False

    await session.commit()
    await session.refresh(verdict)
    return verdict


async def _generate_resume_verdict(application_id: str, organization_id: str) -> None:
    org_uuid = uuid.UUID(organization_id)
    async with org_scoped_session(organization_id) as session:
        application = await session.get(Application, application_id)
        if application is None:
            logger.warning("generate_resume_verdict: application %s not found", application_id)
            return

        resume = await session.get(Resume, str(application.resume_id))
        requisition = await session.get(JobRequisition, str(application.job_requisition_id))
        if resume is None or requisition is None or not resume.parsed_data:
            logger.warning(
                "generate_resume_verdict: application %s missing parsed resume/requisition", application_id
            )
            return

        deterministic_score = resume_fit.score_resume_fit(
            resume.parsed_data, _requisition_requirements(requisition)
        )

        query_text = requisition.title
        required_skills = deterministic_score["matched_skills"] + deterministic_score["missing_skills"]
        if required_skills:
            query_text = f"{requisition.title}. Required skills: {', '.join(required_skills)}"
        query_vectors = await embeddings.embed_chunks([query_text])
        context_chunks: list[str] = []
        if query_vectors:
            retrieved = await vector_store.search(
                org_uuid, query_vectors[0], source_type="resume", source_id=resume.id, limit=5
            )
            context_chunks = [point.payload["chunk_text"] for point in retrieved if point.payload]

        judge_result = judge_agent.run_judge(
            deterministic_score=deterministic_score,
            context_chunks=context_chunks,
            task_description=(
                f"Assess this candidate's resume fit for the '{requisition.title}' requisition."
            ),
        )

        await _upsert_verdict(
            session,
            organization_id=org_uuid,
            application_id=application.id,
            service_type=VerdictServiceType.resume_analysis,
            resume_id=resume.id,
            interview_id=None,
            deterministic_score=deterministic_score,
            verdict_label=VerdictLabel(judge_result["verdict_label"]),
            narrative=judge_result["narrative"],
            crew_run={"judge": get_settings().judge_model},
        )


@celery_app.task(name="app.workers.tasks.verdicts.generate_resume_verdict", base=OrgScopedTask, bind=True)
def generate_resume_verdict(self, application_id: str, organization_id: str) -> None:
    run_async(_generate_resume_verdict(application_id, organization_id))


async def _generate_transcript_verdict(interview_id: str, organization_id: str) -> None:
    org_uuid = uuid.UUID(organization_id)
    async with org_scoped_session(organization_id) as session:
        interview = await session.get(Interview, interview_id)
        if interview is None:
            logger.warning("generate_transcript_verdict: interview %s not found", interview_id)
            return

        if interview.status != InterviewStatus.completed:
            logger.info(
                "generate_transcript_verdict: interview %s not completed (I14), skipping", interview_id
            )
            return

        result = await session.execute(select(Transcript).where(Transcript.interview_id == interview.id))
        transcript = result.scalar_one_or_none()
        if transcript is None or not transcript.text:
            logger.warning(
                "generate_transcript_verdict: no transcript text available for interview %s", interview_id
            )
            return

        deterministic_score = transcript_review.score_transcript(transcript.text)

        query_vectors = await embeddings.embed_chunks([transcript.text[:2000]])
        context_chunks: list[str] = []
        if query_vectors:
            retrieved = await vector_store.search(
                org_uuid, query_vectors[0], source_type="transcript", source_id=transcript.id, limit=5
            )
            context_chunks = [point.payload["chunk_text"] for point in retrieved if point.payload]

        judge_result = judge_agent.run_judge(
            deterministic_score=deterministic_score,
            context_chunks=context_chunks,
            task_description="Review this interview transcript and produce a hiring verdict.",
        )

        await _upsert_verdict(
            session,
            organization_id=org_uuid,
            application_id=interview.application_id,
            service_type=VerdictServiceType.transcript_assignment_review,
            resume_id=None,
            interview_id=interview.id,
            deterministic_score=deterministic_score,
            verdict_label=VerdictLabel(judge_result["verdict_label"]),
            narrative=judge_result["narrative"],
            crew_run={"judge": get_settings().judge_model},
        )


@celery_app.task(name="app.workers.tasks.verdicts.generate_transcript_verdict", base=OrgScopedTask, bind=True)
def generate_transcript_verdict(self, interview_id: str, organization_id: str) -> None:
    run_async(_generate_transcript_verdict(interview_id, organization_id))
