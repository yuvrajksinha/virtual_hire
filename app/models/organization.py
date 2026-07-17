"""Organization — the tenant root. See docs/05-data-model.md#organizations.

VHIRE-1 (E1). Not itself organization_id-scoped (it *is* the scope), so no
RLS policy applies to this table. Creating a row here also provisions a
dedicated Qdrant collection in E3 — this model only owns the Postgres side.
"""

from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import OrganizationStatus


class Organization(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, name="organization_status", create_type=False),
        nullable=False,
        default=OrganizationStatus.active,
        server_default=OrganizationStatus.active.value,
    )
