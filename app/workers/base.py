"""Shared Celery task conventions: org-context propagation for both
storage systems (mirrors app.api.deps for the async task path) and a
common retry/backoff policy.

VHIRE-13 (E5). Every task that touches org-scoped data takes
`organization_id: str` in its payload (Celery payloads are JSON, so ids
travel as strings, not `uuid.UUID`) and uses `org_scoped_session` below to
get an RLS-scoped Postgres session - the same sourcing rule as the request
path applies here: `organization_id` must come from an already-
authenticated context at enqueue time, never re-derived from task content.
"""

import asyncio
from collections.abc import AsyncGenerator, Coroutine
from contextlib import asynccontextmanager
from typing import TypeVar

from celery import Task
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import async_session_maker

T = TypeVar("T")


class OrgScopedTask(Task):
    """Base class for every task that touches org-scoped data.

    Retry/backoff convention: an LLM-call-bound task is treated as one
    retryable unit for v1 (EPIC.md's E5 DoD) - any exception triggers a
    backoff retry up to `max_retries`, rather than silently dropping the
    job.
    """

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    max_retries = 3
    acks_late = True


@asynccontextmanager
async def org_scoped_session(organization_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession with `app.current_org_id` set for RLS (I2) -
    the async-task equivalent of `app.api.deps.get_org_scoped_db`.

    Resolving the org's Qdrant collection name (I11's task-path half) is
    a separate, synchronous call - `app.services.vector_store.collection_name_for_org(uuid.UUID(organization_id))`
    - since it needs no DB round trip; callers do that directly rather
    than through this context manager.
    """
    async with async_session_maker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"),
            {"org_id": str(organization_id)},
        )
        yield session


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Run an async task body from a synchronous Celery task function."""
    return asyncio.run(coro)
