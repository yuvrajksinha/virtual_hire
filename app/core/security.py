"""HR user JWT verification against the managed auth provider's JWKS
endpoint. See docs/06-architecture.md's multi-tenancy section and I2/I3 in
docs/04-invariants.md: organization_id is only ever sourced from a
verified token claim here, never from a client-supplied request field.

VHIRE-2 (E2).
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings
from app.models.enums import HRUserRole


class InvalidCredentialsError(Exception):
    """Raised when a bearer token fails signature, claim, or expiry checks."""


class AuthNotConfiguredError(Exception):
    """Raised when JWT verification is attempted before AUTH_JWKS_URL etc. are set."""


@dataclass(frozen=True)
class HRUserClaims:
    """The verified, request-scoped identity every org-scoped route depends on.

    hr_user_id/organization_id/role come only from a signature-verified
    JWT claim set — this is the single source of truth I2 depends on for
    both the Postgres RLS session variable and Qdrant collection
    resolution (see app.api.deps).
    """

    hr_user_id: uuid.UUID
    organization_id: uuid.UUID
    role: HRUserRole


@lru_cache
def _jwk_client() -> PyJWKClient:
    settings = get_settings()
    if not settings.auth_jwks_url:
        raise AuthNotConfiguredError("AUTH_JWKS_URL is not configured")
    return PyJWKClient(settings.auth_jwks_url)


def decode_hr_jwt(token: str) -> HRUserClaims:
    """Verify `token`'s signature against the JWKS endpoint and extract HR user claims.

    Expected claims: `sub` (hr_user UUID), `org_id` (organization UUID),
    `role` (one of app.models.enums.HRUserRole).

    Raises:
        AuthNotConfiguredError: if AUTH_JWKS_URL is not set.
        InvalidCredentialsError: on any signature, issuer, audience,
            expiry, or claim-shape failure.
    """
    settings = get_settings()
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth_jwt_audience or None,
            issuer=settings.auth_jwt_issuer or None,
        )
    except jwt.PyJWTError as exc:
        raise InvalidCredentialsError(f"token verification failed: {exc}") from exc

    try:
        return HRUserClaims(
            hr_user_id=uuid.UUID(str(payload["sub"])),
            organization_id=uuid.UUID(str(payload["org_id"])),
            role=HRUserRole(payload["role"]),
        )
    except (KeyError, ValueError) as exc:
        raise InvalidCredentialsError(f"token missing/invalid required claims: {exc}") from exc
