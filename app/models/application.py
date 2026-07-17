"""Application. See docs/05-data-model.md#applications.

VHIRE-1 (E1). The partial unique index enforces "at most one active
Application per (Candidate, JobRequisition)" while allowing reapplication
after a terminal outcome. The cross-table organization_id consistency
check (I3) is DB-enforced by a trigger added in the initial migration,
not expressible as a declarative SQLAlchemy constraint.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import ApplicationStatus


class Application(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index(
            "uq_applications_active_candidate_requisition",
            "candidate_id",
            "job_requisition_id",
            unique=True,
            postgresql_where=text("status NOT IN ('rejected', 'withdrawn')"),
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False
    )
    job_requisition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_requisitions.id"), nullable=False
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=False
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status", create_type=False),
        nullable=False,
        default=ApplicationStatus.submitted,
        server_default=ApplicationStatus.submitted.value,
    )
