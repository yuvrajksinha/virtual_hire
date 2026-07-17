"""AnalysisOutput. See docs/05-data-model.md#analysis_outputs.

VHIRE-1 (E1). `source_scorecard_ids` makes the I10 input set auditable
after the fact; the crew's data-fetch step (E9) is what actually enforces
I10 by only ever querying submitted scorecards.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin


class AnalysisOutput(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "analysis_outputs"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary: Mapped[str] = mapped_column(nullable=False)
    match_rationale: Mapped[str | None] = mapped_column(nullable=True)
    source_scorecard_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False
    )
    crew_run: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
