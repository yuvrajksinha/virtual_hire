"""Candidate. See docs/05-data-model.md#candidates.

VHIRE-1 (E1). `pii_deleted_at` is written by E12's I9 deletion routine, not
by anything in this epic.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import CandidateStatus


class Candidate(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_candidates_org_email"),)

    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus, name="candidate_status", create_type=False),
        nullable=False,
        default=CandidateStatus.active,
        server_default=CandidateStatus.active.value,
    )
    pii_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
