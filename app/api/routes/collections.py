"""Collections API (requires Bearer JWT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import get_current_user
from app.schemas.collection import CollectionListResponse, CollectionOut
from app.services.collection_service import list_collections_for_user

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=CollectionListResponse)
def list_collections(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CollectionListResponse:
    """
    Collections for the caller's org memberships.

    Without a Postgres user row: if `VERIFIEDSIGNAL_ALLOW_DEFAULT_COLLECTION_FALLBACK` is true,
    the seeded default inbox may appear (local dev). With auto-provision, the first Bearer request
    creates a personal org + inbox.
    """
    rows = list_collections_for_user(db, auth_sub=user_id)
    return CollectionListResponse(
        collections=[
            CollectionOut(
                id=c.id,
                organization_id=c.organization_id,
                name=c.name,
                slug=c.slug,
                document_count=n,
                created_at=c.created_at,
            )
            for c, n in rows
        ],
    )
