"""Interview. See docs/05-data-model.md#interviews.

VHIRE-1 (E1).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import InterviewStatus


class Interview(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "interviews"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False
    )
    interviewer_hr_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hr_users.id"), nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status", create_type=False),
        nullable=False,
        default=InterviewStatus.scheduled,
        server_default=InterviewStatus.scheduled.value,
    )
