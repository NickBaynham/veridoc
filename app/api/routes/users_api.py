"""User profile helpers (requires Supabase JWT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api.deps import get_db
from app.auth.claims import AccessTokenClaims
from app.auth.dependencies import get_current_user
from app.schemas.user_api import UserMeOut
from app.services.identity_service import find_user_id_by_auth_sub

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeOut)
def read_me(
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> UserMeOut:
    db_uid = find_user_id_by_auth_sub(db, user_id)
    claims = getattr(request.state, "vs_claims", None)
    email: str | None = None
    display_name: str | None = None
    if isinstance(claims, AccessTokenClaims):
        email = claims.email
        display_name = claims.display_name
    return UserMeOut(
        user_id=user_id,
        database_user_id=db_uid,
        email=email,
        display_name=display_name,
    )
