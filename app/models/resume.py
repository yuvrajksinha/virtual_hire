"""Resume. See docs/05-data-model.md#resumes.

VHIRE-1 (E1). `status` is worker-written only (I6) — no API route should
ever accept a client-supplied value for it; `embedding_status` is the
Postgres-side signal for "is this resume searchable" now that the vector
data itself lives in Qdrant (E7), not a Postgres table.
"""

import uuid

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import EmbeddingStatus, ResumeStatus


class Resume(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "resumes"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False
    )
    file_object_key: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[ResumeStatus] = mapped_column(
        Enum(ResumeStatus, name="resume_status", create_type=False),
        nullable=False,
        default=ResumeStatus.uploaded,
        server_default=ResumeStatus.uploaded.value,
    )
    parsed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(nullable=True)
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        Enum(EmbeddingStatus, name="embedding_status", create_type=False),
        nullable=False,
        default=EmbeddingStatus.not_embedded,
        server_default=EmbeddingStatus.not_embedded.value,
    )
    embedding_error: Mapped[str | None] = mapped_column(nullable=True)
