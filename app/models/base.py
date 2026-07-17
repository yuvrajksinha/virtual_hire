"""Shared model mixins.

VHIRE-1 (E1). `TimestampMixin`/`UUIDPkMixin` implement the conventions
stated at the top of docs/05-data-model.md ("all Postgres tables have
id UUID PRIMARY KEY DEFAULT gen_random_uuid() and created_at, updated_at
TIMESTAMPTZ unless noted") so each table module only declares its own
columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class UUIDPkMixin:
    """Adds `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class TimestampMixin:
    """Adds `created_at`/`updated_at TIMESTAMPTZ NOT NULL`, DB-assigned."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OrgScopedMixin:
    """Adds `organization_id UUID NOT NULL REFERENCES organizations(id)`.

    Every table using this mixin is the target of an RLS policy created in
    the initial migration, keyed on this column (enforces I2).
    """

    @declared_attr
    def organization_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
