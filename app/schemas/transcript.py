"""Pydantic response schema for the Transcript resource."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import TranscriptSource, TranscriptStatus


class TranscriptRead(BaseModel):
    """Response body for transcript ingestion/read endpoints."""

    id: uuid.UUID
    interview_id: uuid.UUID
    status: TranscriptStatus
    source: TranscriptSource | None
    language: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
