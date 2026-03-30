"""FastAPI auth dependencies (Bearer JWT → Supabase user id)."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.deps import get_db
from app.auth.jwt_verify import decode_access_token_claims
from app.core.config import Settings, get_settings
from app.services.identity_service import ensure_personal_tenant_for_claims

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validates the Bearer JWT and returns the user_id (`sub` claim).

    When `VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY` is true, ensures a `users` row plus personal
    org/membership/inbox collection exist (idempotent), and commits when inserts occur.

    Never calls Supabase HTTP — verification uses JWKS or shared secret only.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = decode_access_token_claims(credentials.credentials, settings)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None

    request.state.vs_claims = claims

    _, created = ensure_personal_tenant_for_claims(db, claims, settings)
    if created:
        db.commit()

    return claims.sub
