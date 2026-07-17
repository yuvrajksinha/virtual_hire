"""Shared fixtures for tests that need a real Postgres instance.

These tests apply the actual Alembic migration and exercise the DB-layer
enforcement (triggers, RLS policies, constraints) that plain unit tests
against SQLAlchemy metadata can't verify. They're skipped automatically
if DATABASE_URL isn't reachable (e.g. no local Postgres/docker-compose
running) rather than failing the whole suite - CI runs them for real
against a Postgres service container.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def _asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _pg_reachable(dsn: str) -> bool:
    try:
        conn = await asyncpg.connect(dsn)
    except Exception:
        return False
    await conn.close()
    return True


@pytest.fixture(scope="session")
def pg_dsn() -> str:
    return _asyncpg_dsn(get_settings().database_url)


@pytest.fixture(scope="session", autouse=True)
def _migrated_database(pg_dsn: str):
    if not asyncio.run(_pg_reachable(pg_dsn)):
        pytest.skip(f"Postgres not reachable at {pg_dsn}; skipping DB integration tests")

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, check=True
    )
    yield
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"], cwd=REPO_ROOT, check=True
    )


@pytest.fixture
async def conn(pg_dsn: str):
    connection = await asyncpg.connect(pg_dsn)
    try:
        yield connection
    finally:
        await connection.close()
