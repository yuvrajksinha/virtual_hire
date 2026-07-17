"""JobRequisition. See docs/05-data-model.md#job_requisitions.

VHIRE-1 (E1).
"""

import uuid

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import JobRequisitionStatus


class JobRequisition(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "job_requisitions"

    title: Mapped[str] = mapped_column(nullable=False)
    department: Mapped[str | None] = mapped_column(nullable=True)
    owner_hr_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hr_users.id"), nullable=False
    )
    status: Mapped[JobRequisitionStatus] = mapped_column(
        Enum(JobRequisitionStatus, name="job_requisition_status", create_type=False),
        nullable=False,
        default=JobRequisitionStatus.draft,
        server_default=JobRequisitionStatus.draft.value,
    )
    scorecard_template: Mapped[dict] = mapped_column(JSONB, nullable=False)
