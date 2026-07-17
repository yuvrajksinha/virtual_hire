"""Scorecard. See docs/05-data-model.md#scorecards.

VHIRE-1 (E1). I4 (immutability post-submission) is enforced by a trigger
plus an `amend_scorecard` stored procedure added in the initial migration
— not expressible as a declarative SQLAlchemy constraint. This model only
declares the shape of the row; the amendment write path lives in E8.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import ScorecardStatus


class Scorecard(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "scorecards"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False, unique=True
    )
    ratings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[ScorecardStatus] = mapped_column(
        Enum(ScorecardStatus, name="scorecard_status", create_type=False),
        nullable=False,
        default=ScorecardStatus.draft,
        server_default=ScorecardStatus.draft.value,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
