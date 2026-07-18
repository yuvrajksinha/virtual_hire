"""Pydantic response schema for the Application resource returned by
resume submission (VHIRE-13 / E4).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ApplicationStatus


class ApplicationRead(BaseModel):
    """Response body for `POST /applications` (resume submission)."""

    id: uuid.UUID
    organization_id: uuid.UUID
    candidate_id: uuid.UUID
    job_requisition_id: uuid.UUID
    resume_id: uuid.UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
