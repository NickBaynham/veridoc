"""Collections API (requires Bearer JWT)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import get_current_user
from app.schemas.collection import (
    CollectionAnalyticsOut,
    CollectionCreateIn,
    CollectionListResponse,
    CollectionOut,
    CollectionUpdateIn,
)
from app.services.collection_analytics_service import get_collection_analytics
from app.services.collection_mutation_service import (
    create_collection_for_user,
    delete_collection_for_user,
    update_collection_for_user,
)
from app.services.collection_service import list_collections_for_user
from app.services.exceptions import CollectionAccessError, CollectionOrgAccessError

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


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(
    body: CollectionCreateIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CollectionOut:
    """
    Create a collection in an organization you belong to (or the dev default org when permitted).
    """
    try:
        c = create_collection_for_user(
            db,
            user_id,
            name=body.name,
            organization_id=body.organization_id,
        )
    except CollectionOrgAccessError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        msg = str(e)
        if "slug conflict" in msg:
            raise HTTPException(status_code=409, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    return CollectionOut(
        id=c.id,
        organization_id=c.organization_id,
        name=c.name,
        slug=c.slug,
        document_count=0,
        created_at=c.created_at,
    )


@router.get("/{collection_id}/analytics", response_model=CollectionAnalyticsOut)
async def collection_analytics(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CollectionAnalyticsOut:
    """
    Facet counts from the search index plus Postgres rollups on canonical `document_scores`.
    """
    return await get_collection_analytics(db, auth_sub=user_id, collection_id=collection_id)


@router.patch("/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: uuid.UUID,
    body: CollectionUpdateIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CollectionOut:
    """Rename a collection (slug is regenerated from the new name, unique per organization)."""
    try:
        c = update_collection_for_user(db, user_id, collection_id=collection_id, name=body.name)
    except CollectionAccessError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        msg = str(e)
        if "slug conflict" in msg:
            raise HTTPException(status_code=409, detail=msg) from e
        raise HTTPException(status_code=400, detail=msg) from e
    rows = list_collections_for_user(db, auth_sub=user_id)
    count = next((n for col, n in rows if col.id == c.id), 0)
    return CollectionOut(
        id=c.id,
        organization_id=c.organization_id,
        name=c.name,
        slug=c.slug,
        document_count=count,
        created_at=c.created_at,
    )


@router.delete("/{collection_id}", status_code=204)
def delete_collection(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> None:
    """
    Remove a collection you can access.

    Documents in this collection are removed (cascade); this cannot be undone.
    """
    try:
        delete_collection_for_user(db, user_id, collection_id=collection_id)
    except CollectionAccessError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
