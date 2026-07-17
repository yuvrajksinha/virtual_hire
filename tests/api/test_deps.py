"""Tests for app.api.deps (VHIRE-2 / E2): auth, org-scoped DB context,
Qdrant collection resolution, and role enforcement. Uses fakes for the
FastAPI security scheme and DB session rather than a live server/DB -
these test this module's own logic, not HTTP routing or Postgres.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import (
    get_current_hr_user,
    get_org_qdrant_collection,
    get_org_scoped_db,
    require_role,
)
from app.core.security import HRUserClaims, InvalidCredentialsError
from app.models.enums import HRUserRole
from app.services.vector_store import collection_name_for_org


class _FakeCredentials:
    def __init__(self, token: str):
        self.credentials = token


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


def _claims(**overrides) -> HRUserClaims:
    defaults = dict(hr_user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role=HRUserRole.recruiter)
    return HRUserClaims(**{**defaults, **overrides})


async def test_get_current_hr_user_returns_claims_for_a_valid_token(monkeypatch):
    expected = _claims()
    monkeypatch.setattr("app.api.deps.decode_hr_jwt", lambda token: expected)

    result = await get_current_hr_user(_FakeCredentials("valid-token"))

    assert result == expected


async def test_get_current_hr_user_raises_401_for_an_invalid_token(monkeypatch):
    def _raise(token):
        raise InvalidCredentialsError("bad token")

    monkeypatch.setattr("app.api.deps.decode_hr_jwt", _raise)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_hr_user(_FakeCredentials("bad-token"))

    assert exc_info.value.status_code == 401


async def test_get_org_qdrant_collection_resolves_from_claims():
    hr_user = _claims()

    collection = await get_org_qdrant_collection(hr_user)

    assert collection == collection_name_for_org(hr_user.organization_id)


async def test_get_org_scoped_db_sets_current_org_id_and_yields_session():
    hr_user = _claims()
    session = _FakeSession()

    generator = get_org_scoped_db(hr_user=hr_user, session=session)
    yielded = await generator.__anext__()
    try:
        assert yielded is session
        assert len(session.executed) == 1
        sql, params = session.executed[0]
        assert "set_config" in sql
        assert params == {"org_id": str(hr_user.organization_id)}
    finally:
        await generator.aclose()


async def test_require_role_allows_a_matching_role():
    hr_user = _claims(role=HRUserRole.hiring_manager)
    dependency = require_role(HRUserRole.hiring_manager, HRUserRole.recruiter)

    result = await dependency(hr_user)

    assert result == hr_user


async def test_require_role_rejects_a_non_matching_role():
    hr_user = _claims(role=HRUserRole.hr_generalist)
    dependency = require_role(HRUserRole.hiring_manager)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(hr_user)

    assert exc_info.value.status_code == 403
