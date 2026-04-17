"""Collections API (requires Bearer JWT)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import get_current_user
from app.schemas.collection import (
    CollectionActivityResponse,
    CollectionAnalyticsOut,
    CollectionCreateIn,
    CollectionDetailOut,
    CollectionDocumentsListResponse,
    CollectionListResponse,
    CollectionOut,
    CollectionUpdateIn,
)
from app.schemas.knowledge_model import (
    KnowledgeModelCreateIn,
    KnowledgeModelCreateResponse,
    KnowledgeModelListResponse,
)
from app.services.collection_analytics_service import get_collection_analytics
from app.services.collection_detail_service import (
    get_collection_activity_for_user,
    get_collection_detail_for_user,
    list_collection_documents_for_user,
)
from app.services.collection_mutation_service import (
    create_collection_for_user,
    delete_collection_for_user,
    update_collection_for_user,
)
from app.services.collection_service import list_collections_for_user
from app.services.exceptions import CollectionAccessError, CollectionOrgAccessError
from app.services.knowledge_model_service import create_model, list_models_for_collection

router = APIRouter(prefix="/collections", tags=["collections"])

_COLLECTION_DOC_SORT = frozenset({
    "created_at_desc",
    "created_at_asc",
    "name_asc",
    "name_desc",
    "factuality_desc",
    "factuality_asc",
})


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


@router.get("/{collection_id}", response_model=CollectionDetailOut)
def get_collection_detail(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> CollectionDetailOut:
    """Workspace summary: counts, last activity timestamp, status breakdown."""
    out = get_collection_detail_for_user(db, auth_sub=user_id, collection_id=collection_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return out


@router.get("/{collection_id}/models", response_model=KnowledgeModelListResponse)
def list_collection_knowledge_models(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> KnowledgeModelListResponse:
    """List knowledge models in this collection workspace."""
    try:
        return list_models_for_collection(db, auth_sub=user_id, collection_id=collection_id)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Collection not found") from None


@router.post(
    "/{collection_id}/models",
    response_model=KnowledgeModelCreateResponse,
    status_code=201,
)
def create_collection_knowledge_model(
    collection_id: uuid.UUID,
    body: KnowledgeModelCreateIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> KnowledgeModelCreateResponse:
    """Create a knowledge model (version 1) from selected documents and enqueue build."""
    try:
        return create_model(db, auth_sub=user_id, collection_id=collection_id, body=body)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Collection not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{collection_id}/documents", response_model=CollectionDocumentsListResponse)
def list_collection_documents(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[str | None, Query(max_length=64)] = None,
    q: Annotated[str | None, Query(max_length=512)] = None,
    source_kind: Annotated[str | None, Query(max_length=32)] = None,
    sort: Annotated[str, Query(max_length=32)] = "created_at_desc",
) -> CollectionDocumentsListResponse:
    """
    Document directory for a collection: pagination, optional text search on title/filename,
    filter by pipeline `status`, filter by intake `source_kind`, sort.
    """
    if sort not in _COLLECTION_DOC_SORT:
        raise HTTPException(
            status_code=400,
            detail=f"invalid sort; allowed: {sorted(_COLLECTION_DOC_SORT)}",
        )
    out = list_collection_documents_for_user(
        db,
        auth_sub=user_id,
        collection_id=collection_id,
        limit=limit,
        offset=offset,
        status=status,
        q=q,
        source_kind=source_kind,
        sort=sort,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return out


@router.get("/{collection_id}/activity", response_model=CollectionActivityResponse)
def get_collection_activity(
    collection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> CollectionActivityResponse:
    """Recent pipeline events for documents in this workspace (newest first)."""
    out = get_collection_activity_for_user(
        db,
        auth_sub=user_id,
        collection_id=collection_id,
        limit=limit,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return out


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
