"""Parsing Worker: fetch a resume file, run the Extraction Agent, write
`parsed_data`, enqueue embedding. See EPIC.md's E6 and docs/06-architecture.md's
Parsing Worker row.

VHIRE-2x (E6). Failure path always sets `status=parse_failed` +
`parse_error` - never left stuck in `parsing` (I6).
"""

import logging

from app.crew.agents.extraction import extract_resume_fields
from app.models.enums import ResumeStatus
from app.models.resume import Resume
from app.services import storage, text_extraction
from app.workers.base import OrgScopedTask, org_scoped_session, run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _parse_resume(resume_id: str, organization_id: str) -> None:
    async with org_scoped_session(organization_id) as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            logger.warning("parse_resume: resume %s not found for org %s", resume_id, organization_id)
            return

        resume.status = ResumeStatus.parsing
        await session.flush()

        try:
            file_content = storage.download_object(resume.file_object_key)
            resume_text = text_extraction.extract_text(file_content, resume.file_object_key)
            parsed_data = extract_resume_fields(resume_text)
        except Exception as exc:
            resume.status = ResumeStatus.parse_failed
            resume.parse_error = str(exc)
            await session.commit()
            return

        resume.parsed_data = parsed_data
        resume.parse_error = None
        resume.status = ResumeStatus.parsed
        await session.commit()

    celery_app.send_task(
        "app.workers.tasks.embedding.embed_resume",
        kwargs={"resume_id": resume_id, "organization_id": organization_id},
    )


@celery_app.task(name="app.workers.tasks.parsing.parse_resume", base=OrgScopedTask, bind=True)
def parse_resume(self, resume_id: str, organization_id: str) -> None:
    run_async(_parse_resume(resume_id, organization_id))
