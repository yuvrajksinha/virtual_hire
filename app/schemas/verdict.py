"""Pydantic response schema for the Verdict resource (RAG-driven Scoring
Engine + Judge output).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import VerdictLabel, VerdictServiceType


class VerdictRead(BaseModel):
    """Response body for verdict-fetch endpoints. Never exposes a bare
    numeric score - `verdict_label` + `narrative` only, per the
    "narrative over score" posture in docs/00-ideation.md.
    """

    id: uuid.UUID
    application_id: uuid.UUID
    service_type: VerdictServiceType
    verdict_label: VerdictLabel
    narrative: str
    generated_at: datetime
    stale: bool

    model_config = {"from_attributes": True}
