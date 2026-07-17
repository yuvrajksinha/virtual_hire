"""Tests for app.core.security (VHIRE-2 / E2): HR-user JWT verification.

A fake PyJWKClient stands in for the real JWKS HTTP fetch so these run
without network access - only the signature/claim verification logic
(the part this module owns) is under test.
"""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import security
from app.core.config import get_settings
from app.core.security import (
    AuthNotConfiguredError,
    HRUserClaims,
    InvalidCredentialsError,
    decode_hr_jwt,
)
from app.models.enums import HRUserRole


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_pem, private_key.public_key()


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKClient:
    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(self._public_key)


def _use_fake_jwks(monkeypatch, public_key):
    monkeypatch.setattr(security, "_jwk_client", lambda: _FakeJWKClient(public_key))


def _token(private_pem, **overrides) -> str:
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "org_id": str(uuid.uuid4()),
        "role": HRUserRole.recruiter.value,
        "iat": now,
        "exp": now + 300,
        **overrides,
    }
    return jwt.encode(payload, private_pem, algorithm="RS256")


def test_decode_hr_jwt_returns_claims_for_a_valid_token(monkeypatch, keypair):
    private_pem, public_key = keypair
    _use_fake_jwks(monkeypatch, public_key)
    hr_user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = _token(private_pem, sub=str(hr_user_id), org_id=str(org_id), role="hiring_manager")

    claims = decode_hr_jwt(token)

    assert claims == HRUserClaims(
        hr_user_id=hr_user_id, organization_id=org_id, role=HRUserRole.hiring_manager
    )


def test_decode_hr_jwt_rejects_expired_token(monkeypatch, keypair):
    private_pem, public_key = keypair
    _use_fake_jwks(monkeypatch, public_key)
    token = _token(private_pem, exp=int(time.time()) - 10)

    with pytest.raises(InvalidCredentialsError):
        decode_hr_jwt(token)


def test_decode_hr_jwt_rejects_token_signed_by_a_different_key(monkeypatch, keypair):
    _, public_key = keypair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_private_pem = other_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _use_fake_jwks(monkeypatch, public_key)
    token = _token(other_private_pem)

    with pytest.raises(InvalidCredentialsError):
        decode_hr_jwt(token)


@pytest.mark.parametrize("missing_claim", ["sub", "org_id", "role"])
def test_decode_hr_jwt_rejects_token_missing_required_claim(monkeypatch, keypair, missing_claim):
    private_pem, public_key = keypair
    _use_fake_jwks(monkeypatch, public_key)
    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "org_id": str(uuid.uuid4()),
        "role": HRUserRole.recruiter.value,
        "iat": now,
        "exp": now + 300,
    }
    del payload[missing_claim]
    token = jwt.encode(payload, private_pem, algorithm="RS256")

    with pytest.raises(InvalidCredentialsError):
        decode_hr_jwt(token)


def test_decode_hr_jwt_rejects_unknown_role(monkeypatch, keypair):
    private_pem, public_key = keypair
    _use_fake_jwks(monkeypatch, public_key)
    token = _token(private_pem, role="superadmin")

    with pytest.raises(InvalidCredentialsError):
        decode_hr_jwt(token)


def test_decode_hr_jwt_enforces_configured_issuer_and_audience(monkeypatch, keypair):
    private_pem, public_key = keypair
    monkeypatch.setenv("AUTH_JWT_ISSUER", "https://auth.sift.test/")
    monkeypatch.setenv("AUTH_JWT_AUDIENCE", "sift-api")
    _use_fake_jwks(monkeypatch, public_key)

    good_token = _token(private_pem, iss="https://auth.sift.test/", aud="sift-api")
    assert decode_hr_jwt(good_token).role == HRUserRole.recruiter

    wrong_audience_token = _token(private_pem, iss="https://auth.sift.test/", aud="other-api")
    with pytest.raises(InvalidCredentialsError):
        decode_hr_jwt(wrong_audience_token)


def test_decode_hr_jwt_raises_when_jwks_url_not_configured(monkeypatch):
    monkeypatch.setenv("AUTH_JWKS_URL", "")
    security._jwk_client.cache_clear()

    with pytest.raises(AuthNotConfiguredError):
        decode_hr_jwt("irrelevant")
