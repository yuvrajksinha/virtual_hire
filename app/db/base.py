"""Async SQLAlchemy engine/session setup.

VHIRE-1 (E1). See docs/05-data-model.md for the schema this session talks to
and docs/06-architecture.md for the org-scoped-transaction pattern app/api/deps.py
(E2) builds on top of get_db.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base every ORM model inherits from.

    `app.models` imports every model module so this metadata is complete
    before Alembic autogenerate or `Base.metadata.create_all` run.
    """


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a plain (not org-scoped) AsyncSession.

    Use directly only for code with no RLS-relevant tenant data (none in
    this schema yet). Request handlers that touch tenant tables should
    depend on app.api.deps.get_org_scoped_db instead, which wraps this
    session in a transaction with `app.current_org_id` set for I2.
    """
    async with async_session_maker() as session:
        yield session
