"""
Supabase Auth pass-through: signup, login (refresh cookie), refresh, logout, reset email.

Thin wrappers around supabase-py GoTrue client; JWT validation for API routes lives in
`app.auth.dependencies` (JWKS / HS256 only — no Supabase round-trip per request).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, TypeVar

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from supabase_auth.errors import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthSessionMissingError,
    AuthWeakPasswordError,
)

from app.api.deps import get_db
from app.auth.jwt_verify import decode_access_token_claims
from app.auth.supabase_service import get_supabase_service_client
from app.core.config import Settings, get_settings
from app.rate_limit import limiter
from app.schemas.auth_api import (
    AccessTokenResponse,
    EmailPasswordBody,
    RefreshResponse,
    ResetPasswordBody,
    SignupResponse,
)
from app.schemas.user_api import SyncIdentityOut
from app.services.identity_service import (
    ensure_personal_tenant_for_claims,
    find_user_id_by_auth_sub,
    list_tenant_ids_for_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

sync_bearer = HTTPBearer(auto_error=True)

REFRESH_COOKIE = "vs_refresh_token"
REFRESH_MAX_AGE = 7 * 24 * 3600
COOKIE_PATH = "/auth"

_SUPABASE_UNREACHABLE_DETAIL = (
    "Cannot reach Supabase (check SUPABASE_URL and that `supabase start` is running). "
    "For local GoTrue use http://127.0.0.1:54321 in .env — the API rewrites that to "
    "host.docker.internal automatically when it runs inside Docker."
)

T = TypeVar("T")


def _supabase_auth_call(func: Callable[[], T]) -> T:
    """Map transport errors from GoTrue HTTP calls to HTTP errors (avoid raw 500)."""
    try:
        return func()
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_SUPABASE_UNREACHABLE_DETAIL,
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Supabase did not respond in time (check SUPABASE_URL and network).",
        ) from e


def _require_supabase_config(settings: Settings) -> None:
    if not settings.supabase_auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth is not configured (set SUPABASE_URL and keys)",
        )


def _auth_error_detail(exc: AuthApiError) -> str:
    return getattr(exc, "message", None) or str(exc)


@router.post("/signup", response_model=SignupResponse)
@limiter.limit(lambda: get_settings().rate_limit_auth_signup)
def auth_signup(
    request: Request,
    body: EmailPasswordBody,
    settings: Settings = Depends(get_settings),
) -> SignupResponse:
    _require_supabase_config(settings)
    client = get_supabase_service_client()
    try:
        _supabase_auth_call(
            lambda: client.auth.sign_up({"email": body.email, "password": body.password}),
        )
    except AuthWeakPasswordError as e:
        raise HTTPException(status_code=400, detail=_auth_error_detail(e)) from e
    except AuthApiError as e:
        code = getattr(e, "code", None) or getattr(e, "name", "") or ""
        if "exists" in str(code).lower() or "already" in _auth_error_detail(e).lower():
            raise HTTPException(status_code=400, detail="Email already registered") from e
        raise HTTPException(status_code=400, detail=_auth_error_detail(e)) from e
    return SignupResponse()


@router.post("/sync-identity", response_model=SyncIdentityOut)
@limiter.limit(lambda: get_settings().rate_limit_auth_sync_identity)
def auth_sync_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(sync_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncIdentityOut:
    """
    Ensure Postgres `users` + personal org + `organization_members` + inbox `collections` exist.

    Call after login if the SPA prefers an explicit hook; otherwise the first `Authorization`
    request with auto-provision enabled already performs the same work.
    """
    try:
        claims = decode_access_token_claims(credentials.credentials, settings)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None

    _, created = ensure_personal_tenant_for_claims(db, claims, settings)
    if created:
        db.commit()

    db_uid = find_user_id_by_auth_sub(db, claims.sub)
    if db_uid is None:
        raise HTTPException(
            status_code=403,
            detail=(
                "No Postgres user linked to this token. Enable "
                "VERIFIEDSIGNAL_AUTO_PROVISION_IDENTITY or create users/organization_members "
                "manually."
            ),
        )
    org_ids, col_ids = list_tenant_ids_for_user(db, db_uid)
    return SyncIdentityOut(
        database_user_id=db_uid,
        organization_ids=org_ids,
        collection_ids=col_ids,
    )


@router.post("/login", response_model=AccessTokenResponse)
@limiter.limit(lambda: get_settings().rate_limit_auth_login)
def auth_login(
    request: Request,
    body: EmailPasswordBody,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    _require_supabase_config(settings)
    client = get_supabase_service_client()
    try:
        res = _supabase_auth_call(
            lambda: client.auth.sign_in_with_password(
                {"email": body.email, "password": body.password},
            ),
        )
    except AuthInvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail="Invalid email or password") from e
    except AuthApiError as e:
        raise HTTPException(status_code=401, detail=_auth_error_detail(e)) from e
    session = res.session
    if session is None:
        raise HTTPException(
            status_code=401,
            detail="No session returned (confirm your email if required)",
        )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=session.refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        max_age=REFRESH_MAX_AGE,
        path=COOKIE_PATH,
    )
    return AccessTokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
    )


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit(lambda: get_settings().rate_limit_auth_refresh)
def auth_refresh(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> RefreshResponse:
    _require_supabase_config(settings)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    client = get_supabase_service_client()
    try:
        res = _supabase_auth_call(lambda: client.auth.refresh_session(refresh_token))
    except (AuthApiError, AuthSessionMissingError) as e:
        raise HTTPException(status_code=401, detail="Refresh failed") from e
    session = res.session
    if session is None:
        raise HTTPException(status_code=401, detail="Refresh failed")
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=session.refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        max_age=REFRESH_MAX_AGE,
        path=COOKIE_PATH,
    )
    return RefreshResponse(access_token=session.access_token, expires_in=session.expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().rate_limit_auth_logout)
def auth_logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    _require_supabase_config(settings)
    client = get_supabase_service_client()
    if refresh_token:
        try:
            client.auth.refresh_session(refresh_token)
            client.auth.sign_out()
        except (AuthApiError, AuthSessionMissingError):
            pass
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit(lambda: get_settings().rate_limit_auth_reset)
def auth_reset_password(
    request: Request,
    body: ResetPasswordBody,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _require_supabase_config(settings)
    client = get_supabase_service_client()
    try:
        _supabase_auth_call(lambda: client.auth.reset_password_for_email(body.email))
    except AuthApiError:
        pass
    return {"message": "ok"}
