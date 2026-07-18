"""Resume submission: the synchronous half of the ingestion flow in
docs/06-architecture.md's sequence diagram - accept a resume file, store
it, create/reuse the Candidate, create the Resume and Application rows,
and enqueue parsing. Run inline on the request path (not a separate
deploy), per the architecture doc.

VHIRE-13 (E4).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.application import Application
from app.models.candidate import Candidate
from app.models.enums import ApplicationStatus, EmbeddingStatus, ResumeStatus
from app.models.resume import Resume
from app.services import storage
from app.workers.celery_app import celery_app


async def _get_or_create_candidate(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    email: str,
    full_name: str,
    phone: str | None,
) -> Candidate:
    """Create-or-reuse a Candidate by (organization_id, email), per A8's dedup key."""
    result = await session.execute(
        select(Candidate).where(Candidate.organization_id == organization_id, Candidate.email == email)
    )
    candidate = result.scalar_one_or_none()
    if candidate is not None:
        return candidate

    candidate = Candidate(organization_id=organization_id, email=email, full_name=full_name, phone=phone)
    session.add(candidate)
    await session.flush()
    return candidate


async def submit_resume(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    job_requisition_id: uuid.UUID,
    candidate_email: str,
    candidate_full_name: str,
    candidate_phone: str | None,
    filename: str,
    file_content: bytes,
) -> Application:
    """Accept a resume submission: dedup the Candidate, store the file,
    create Resume + Application in one transaction, and enqueue parsing.

    Respects the partial-unique-active-application constraint already
    enforced at the DB layer on `applications` (I3) - a second active
    submission for the same (Candidate, JobRequisition) raises the
    underlying `IntegrityError`, left to the caller/route to translate
    into a 409.
    """
    candidate = await _get_or_create_candidate(
        session,
        organization_id=organization_id,
        email=candidate_email,
        full_name=candidate_full_name,
        phone=candidate_phone,
    )

    resume_id = uuid.uuid4()
    object_key = storage.object_key_for_resume(organization_id, resume_id, filename)
    await run_in_threadpool(storage.upload_object, key=object_key, content=file_content)

    resume = Resume(
        id=resume_id,
        organization_id=organization_id,
        candidate_id=candidate.id,
        file_object_key=object_key,
        status=ResumeStatus.uploaded,
        embedding_status=EmbeddingStatus.not_embedded,
    )
    session.add(resume)
    await session.flush()

    application = Application(
        organization_id=organization_id,
        candidate_id=candidate.id,
        job_requisition_id=job_requisition_id,
        resume_id=resume.id,
        status=ApplicationStatus.submitted,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)

    celery_app.send_task(
        "app.workers.tasks.parsing.parse_resume",
        kwargs={"resume_id": str(resume.id), "organization_id": str(organization_id)},
    )

    return application
