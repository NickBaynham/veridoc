"""Knowledge model detail APIs (scoped by model id)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.dependencies import get_current_user
from app.schemas.knowledge_model import (
    KnowledgeModelAssetListResponse,
    KnowledgeModelDetailOut,
    KnowledgeModelVersionDetailOut,
    KnowledgeModelVersionListResponse,
)
from app.services.knowledge_model_service import (
    get_model_detail,
    get_version_detail,
    list_version_assets,
    list_versions,
)

router = APIRouter(prefix="/models", tags=["knowledge-models"])


@router.get("/{model_id}", response_model=KnowledgeModelDetailOut)
def get_knowledge_model(
    model_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> KnowledgeModelDetailOut:
    out = get_model_detail(db, auth_sub=user_id, model_id=model_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return out


@router.get("/{model_id}/versions", response_model=KnowledgeModelVersionListResponse)
def list_knowledge_model_versions(
    model_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> KnowledgeModelVersionListResponse:
    out = list_versions(db, auth_sub=user_id, model_id=model_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return out


@router.get(
    "/{model_id}/versions/{version_id}",
    response_model=KnowledgeModelVersionDetailOut,
)
def get_knowledge_model_version(
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> KnowledgeModelVersionDetailOut:
    out = get_version_detail(db, auth_sub=user_id, model_id=model_id, version_id=version_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Model or version not found")
    return out


@router.get(
    "/{model_id}/versions/{version_id}/assets",
    response_model=KnowledgeModelAssetListResponse,
)
def list_knowledge_model_version_assets(
    model_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> KnowledgeModelAssetListResponse:
    out = list_version_assets(db, auth_sub=user_id, model_id=model_id, version_id=version_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Model or version not found")
    return out
