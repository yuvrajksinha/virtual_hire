"""Shared FastAPI request dependencies: HR-user auth, org-scoped DB
transactions, Qdrant collection resolution, and role enforcement.

VHIRE-2 (E2). Every org-scoped route depends on `get_org_scoped_db` (or,
if it also needs the raw claims/collection name, composes
`get_current_hr_user`/`get_org_qdrant_collection` alongside it) rather
than `app.db.base.get_db` directly — this is what makes I2 the default,
not an opt-in.
"""

from collections.abc import AsyncGenerator, Callable, Coroutine

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import HRUserClaims, InvalidCredentialsError, decode_hr_jwt
from app.db.base import get_db
from app.models.enums import HRUserRole
from app.services.vector_store import collection_name_for_org

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_hr_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> HRUserClaims:
    """Verify the request's bearer token and return its HR user claims.

    Raises:
        HTTPException: 401 if the token is missing, malformed, expired,
            or fails signature verification.
    """
    try:
        return decode_hr_jwt(credentials.credentials)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired credentials"
        ) from exc


async def get_org_scoped_db(
    hr_user: HRUserClaims = Depends(get_current_hr_user),
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session inside a transaction with `app.current_org_id` set for RLS.

    This is the DB-layer half of I2: `organization_id` here comes only
    from the verified token claims, never a client-supplied field, and
    every query issued through `session` is scoped by the RLS policies
    created in the VHIRE-1 migration.
    """
    async with session.begin():
        await session.execute(
            text("SELECT set_config('app.current_org_id', :org_id, true)"),
            {"org_id": str(hr_user.organization_id)},
        )
        yield session


async def get_org_qdrant_collection(hr_user: HRUserClaims = Depends(get_current_hr_user)) -> str:
    """Resolve the requesting HR user's Qdrant collection name (I11).

    Resolved the same way as the RLS session variable: server-side, from
    the verified token, never from a client-supplied field.
    """
    return collection_name_for_org(hr_user.organization_id)


def require_role(
    *allowed_roles: HRUserRole,
) -> Callable[[HRUserClaims], Coroutine[None, None, HRUserClaims]]:
    """Build a dependency that only admits HR users whose role is in `allowed_roles`.

    Raises:
        HTTPException: 403 if the authenticated HR user's role isn't allowed.
    """

    async def _check(hr_user: HRUserClaims = Depends(get_current_hr_user)) -> HRUserClaims:
        if hr_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role for this operation"
            )
        return hr_user

    return _check
