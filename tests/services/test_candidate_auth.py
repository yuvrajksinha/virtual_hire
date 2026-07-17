"""Tests for app.services.candidate_auth (VHIRE-2 / E2): candidate
magic-link token issuance and verification (A9 - no password).
"""

import time
import uuid

import jwt
import pytest

from app.core.config import get_settings
from app.services.candidate_auth import (
    CandidateMagicLinkClaims,
    InvalidMagicLinkError,
    MagicLinkNotConfiguredError,
    issue_magic_link_token,
    verify_magic_link_token,
)


@pytest.fixture(autouse=True)
def _configure_magic_link_secret(monkeypatch):
    monkeypatch.setenv("MAGIC_LINK_SECRET_KEY", "test-secret-do-not-use-in-prod")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_issue_then_verify_round_trips_claims():
    candidate_id = uuid.uuid4()
    organization_id = uuid.uuid4()

    token = issue_magic_link_token(candidate_id, organization_id, "candidate@example.test")
    claims = verify_magic_link_token(token)

    assert claims == CandidateMagicLinkClaims(
        candidate_id=candidate_id, organization_id=organization_id, email="candidate@example.test"
    )


def test_verify_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("MAGIC_LINK_TTL_SECONDS", "1")
    get_settings.cache_clear()
    token = issue_magic_link_token(uuid.uuid4(), uuid.uuid4(), "candidate@example.test")

    expired_token = jwt.encode(
        {**jwt.decode(token, options={"verify_signature": False}), "exp": int(time.time()) - 10},
        get_settings().magic_link_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(InvalidMagicLinkError):
        verify_magic_link_token(expired_token)


def test_verify_rejects_token_signed_with_wrong_secret(monkeypatch):
    token = issue_magic_link_token(uuid.uuid4(), uuid.uuid4(), "candidate@example.test")
    monkeypatch.setenv("MAGIC_LINK_SECRET_KEY", "a-different-secret")
    get_settings.cache_clear()

    with pytest.raises(InvalidMagicLinkError):
        verify_magic_link_token(token)


def test_verify_rejects_a_non_magic_link_token():
    other_token = jwt.encode(
        {"type": "something_else", "sub": str(uuid.uuid4())},
        get_settings().magic_link_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(InvalidMagicLinkError):
        verify_magic_link_token(other_token)


def test_issue_raises_when_secret_not_configured(monkeypatch):
    monkeypatch.setenv("MAGIC_LINK_SECRET_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(MagicLinkNotConfiguredError):
        issue_magic_link_token(uuid.uuid4(), uuid.uuid4(), "candidate@example.test")
