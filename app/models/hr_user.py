"""HRUser — org-scoped staff account. See docs/05-data-model.md#hr_users.

VHIRE-1 (E1). Enforces I2's RLS root (via OrgScopedMixin) and A2/A3
(single-org membership, fixed role enum) from docs/02-assumptions.md.
"""

from sqlalchemy import Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import HRUserRole, HRUserStatus


class HRUser(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "hr_users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_hr_users_org_email"),)

    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[HRUserRole] = mapped_column(
        Enum(HRUserRole, name="hr_user_role", create_type=False), nullable=False
    )
    status: Mapped[HRUserStatus] = mapped_column(
        Enum(HRUserStatus, name="hr_user_status", create_type=False),
        nullable=False,
        default=HRUserStatus.invited,
        server_default=HRUserStatus.invited.value,
    )
