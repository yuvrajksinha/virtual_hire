"""Tests for app.workers.base (VHIRE-13 / E5): org-context propagation for
the async task path and the sync/async bridge. Uses fakes for the DB
session rather than live Postgres - mirrors tests/api/test_deps.py's
approach for the request-path equivalent of this same pattern.
"""

from app.workers.base import org_scoped_session, run_async


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeSession:
    def __init__(self):
        self.executed: list[tuple[str, dict]] = []

    def begin(self):
        return _FakeTransaction()

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


async def test_org_scoped_session_sets_current_org_id(monkeypatch):
    fake_session = _FakeSession()
    monkeypatch.setattr("app.workers.base.async_session_maker", lambda: fake_session)

    async with org_scoped_session("11111111-1111-1111-1111-111111111111") as session:
        assert session is fake_session

    assert len(fake_session.executed) == 1
    sql, params = fake_session.executed[0]
    assert "set_config" in sql
    assert params == {"org_id": "11111111-1111-1111-1111-111111111111"}


def test_run_async_runs_a_coroutine_and_returns_its_result():
    async def _coro():
        return 42

    assert run_async(_coro()) == 42
