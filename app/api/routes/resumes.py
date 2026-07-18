"""Resume submission route (VHIRE-13 / E4). Org-scoped via
`app.api.deps.get_org_scoped_db` - this is an HR-facing intake endpoint
(e.g. an internal referral form or an HR user submitting on a candidate's
behalf); the standalone public/candidate-facing and email-in intake
channels from EPIC.md's E4 ships list are not built in this story.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_hr_user, get_org_scoped_db
from app.core.security import HRUserClaims
from app.schemas.application import ApplicationRead
from app.services import ingestion

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_202_ACCEPTED)
async def submit_resume(
    job_requisition_id: uuid.UUID = Form(...),
    candidate_email: str = Form(...),
    candidate_full_name: str = Form(...),
    candidate_phone: str | None = Form(None),
    file: UploadFile = File(...),
    hr_user: HRUserClaims = Depends(get_current_hr_user),
    session: AsyncSession = Depends(get_org_scoped_db),
) -> ApplicationRead:
    """Submit a candidate's resume against a requisition.

    Creates/reuses the Candidate, uploads the file to object storage,
    creates Resume + Application, and enqueues `parse_resume` (E5/E6).
    """
    file_content = await file.read()
    return await ingestion.submit_resume(
        session,
        organization_id=hr_user.organization_id,
        job_requisition_id=job_requisition_id,
        candidate_email=candidate_email,
        candidate_full_name=candidate_full_name,
        candidate_phone=candidate_phone,
        filename=file.filename or "resume",
        file_content=file_content,
    )
