"""Candidate-side magic-link authentication (no password, per A9 in
docs/02-assumptions.md): a time-limited, signed token emailed to the
candidate that proves control of their email address for a single
organization/candidate pair.

VHIRE-2 (E2). Symmetric (HS256) signing is deliberate here, unlike the
HR-user path in app.core.security: candidates aren't issued credentials
by an external IdP, so there's no JWKS endpoint to verify against.
"""

import time
import uuid
from dataclasses import dataclass

import jwt

from app.core.config import get_settings

_TOKEN_TYPE = "candidate_magic_link"


class MagicLinkNotConfiguredError(Exception):
    """Raised when magic-link issuance/verification is attempted before MAGIC_LINK_SECRET_KEY is set."""


class InvalidMagicLinkError(Exception):
    """Raised when a magic-link token fails signature, expiry, or claim-shape checks."""


@dataclass(frozen=True)
class CandidateMagicLinkClaims:
    candidate_id: uuid.UUID
    organization_id: uuid.UUID
    email: str


def _secret_key() -> str:
    secret = get_settings().magic_link_secret_key
    if not secret:
        raise MagicLinkNotConfiguredError("MAGIC_LINK_SECRET_KEY is not configured")
    return secret


def issue_magic_link_token(candidate_id: uuid.UUID, organization_id: uuid.UUID, email: str) -> str:
    """Issue a signed, time-limited token for `candidate_id` to embed in an email link.

    Raises:
        MagicLinkNotConfiguredError: if MAGIC_LINK_SECRET_KEY is not set.
    """
    settings = get_settings()
    now = int(time.time())
    payload = {
        "type": _TOKEN_TYPE,
        "sub": str(candidate_id),
        "org_id": str(organization_id),
        "email": email,
        "iat": now,
        "exp": now + settings.magic_link_ttl_seconds,
    }
    return jwt.encode(payload, _secret_key(), algorithm="HS256")


def verify_magic_link_token(token: str) -> CandidateMagicLinkClaims:
    """Verify `token`'s signature/expiry and extract candidate identity claims.

    Raises:
        MagicLinkNotConfiguredError: if MAGIC_LINK_SECRET_KEY is not set.
        InvalidMagicLinkError: on any signature, expiry, type, or claim-shape failure.
    """
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidMagicLinkError(f"token verification failed: {exc}") from exc

    if payload.get("type") != _TOKEN_TYPE:
        raise InvalidMagicLinkError("token is not a candidate magic-link token")

    try:
        return CandidateMagicLinkClaims(
            candidate_id=uuid.UUID(str(payload["sub"])),
            organization_id=uuid.UUID(str(payload["org_id"])),
            email=str(payload["email"]),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidMagicLinkError(f"token missing/invalid required claims: {exc}") from exc
