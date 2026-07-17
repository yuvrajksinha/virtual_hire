"""Smoke tests for app.db.base (VHIRE-1 / E1). No DB connection required -
engine/sessionmaker construction is lazy; see tests/integration for tests
that actually hit Postgres.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.base import Base, async_session_maker, engine, get_db


def test_engine_is_async_and_matches_settings_url():
    assert isinstance(engine, AsyncEngine)
    assert engine.url.drivername == "postgresql+asyncpg"


def test_session_maker_produces_async_sessions():
    assert isinstance(async_session_maker, async_sessionmaker)
    assert async_session_maker.kw.get("expire_on_commit") is False


def test_base_metadata_is_a_shared_declarative_registry():
    assert isinstance(Base.metadata.tables, dict)


async def test_get_db_yields_an_async_session():
    generator = get_db()
    session = await generator.__anext__()
    try:
        assert isinstance(session, AsyncSession)
    finally:
        await generator.aclose()
