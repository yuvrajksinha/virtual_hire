"""Verdict fetch routes (RAG-driven Scoring Engine + Judge, "scorecard
logic"). Org-scoped via app.api.deps.get_org_scoped_db. Mirrors EPIC.md's
E9 summary-fetch pattern: fetch the current Verdict, lazily triggering
regeneration via Celery if none exists yet or the existing one is
flagged `stale`, rather than blocking the request on a synchronous LLM
call - matching the sync/async boundary every other epic in this
codebase follows.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_hr_user, get_org_scoped_db
from app.core.security import HRUserClaims
from app.models.enums import VerdictServiceType
from app.models.interview import Interview
from app.models.verdict import Verdict
from app.schemas.verdict import VerdictRead
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/applications", tags=["verdicts"])


async def _maybe_trigger_regeneration(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    organization_id: uuid.UUID,
    service_type: VerdictServiceType,
) -> None:
    """Enqueue regeneration for `service_type`, resolving each task's own
    natural key (an Application for resume verdicts, the most recent
    Interview for transcript verdicts - see `generate_transcript_verdict`'s
    signature in app.workers.tasks.verdicts).
    """
    if service_type == VerdictServiceType.resume_analysis:
        celery_app.send_task(
            "app.workers.tasks.verdicts.generate_resume_verdict",
            kwargs={"application_id": str(application_id), "organization_id": str(organization_id)},
        )
        return

    result = await session.execute(
        select(Interview.id)
        .where(Interview.application_id == application_id)
        .order_by(Interview.scheduled_at.desc())
    )
    interview_id = result.scalars().first()
    if interview_id is not None:
        celery_app.send_task(
            "app.workers.tasks.verdicts.generate_transcript_verdict",
            kwargs={"interview_id": str(interview_id), "organization_id": str(organization_id)},
        )


@router.get("/{application_id}/verdicts/{service_type}", response_model=VerdictRead)
async def read_verdict(
    application_id: uuid.UUID,
    service_type: VerdictServiceType,
    hr_user: HRUserClaims = Depends(get_current_hr_user),
    session: AsyncSession = Depends(get_org_scoped_db),
) -> VerdictRead:
    """Fetch an Application's current Verdict for `service_type`.

    Raises:
        HTTPException: 404 if no Verdict exists yet - a generation job
            has just been enqueued in that case; poll again shortly.
    """
    result = await session.execute(
        select(Verdict).where(Verdict.application_id == application_id, Verdict.service_type == service_type)
    )
    verdict = result.scalar_one_or_none()

    if verdict is None or verdict.stale:
        await _maybe_trigger_regeneration(
            session,
            application_id=application_id,
            organization_id=hr_user.organization_id,
            service_type=service_type,
        )

    if verdict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="verdict not yet generated; regeneration has been enqueued",
        )
    return verdict
