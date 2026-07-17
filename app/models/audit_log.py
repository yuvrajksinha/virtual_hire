"""AuditLog. See docs/05-data-model.md#audit_log.

VHIRE-1 (E1). Append-only by DB trigger (added in the initial migration,
not expressible declaratively) — this table is itself the I4 audit trail
enforcement mechanism. No model-level API for update/delete is exposed
anywhere in this codebase; the trigger is the actual backstop.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, UUIDPkMixin


class AuditLog(UUIDPkMixin, OrgScopedMixin, Base):
    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(nullable=False)
    actor_hr_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hr_users.id"), nullable=False
    )
    diff: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
