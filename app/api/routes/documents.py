"""Document intake: multipart upload, canonical Postgres row, storage, enqueue."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_object_storage_dep
from app.auth.dependencies import get_current_user
from app.schemas.document import (
    DocumentDetailOut,
    DocumentListResponse,
    DocumentSourceOut,
    DocumentSummaryOut,
    IntakeResponse,
    UrlIntakeRequest,
    UrlIntakeResponse,
)
from app.services.document_service import (
    delete_document_for_user,
    get_document_for_user,
    list_documents_for_user,
    run_file_intake,
    run_url_intake_submit,
)
from app.services.exceptions import IntakeValidationError, StorageUploadError
from app.services.storage_service import ObjectStorage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """
    List documents in collections the caller can access (org membership; optional dev fallback).
    """
    items, total = list_documents_for_user(db, auth_sub=user_id, limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentSummaryOut.model_validate(d) for d in items],
        total=total,
        user_id=user_id,
    )


@router.post("/from-url", response_model=UrlIntakeResponse, status_code=202)
def ingest_document_from_url(
    body: UrlIntakeRequest,
    db: Session = Depends(get_db),
    _user_id: str = Depends(get_current_user),
) -> UrlIntakeResponse:
    """
    Accept a remote URL: `created` row + `url` source, then worker fetch → S3 → pipeline.

    Poll `GET /documents/{id}` for `queued` / `failed` after the fetch job completes.
    """
    _ = _user_id
    try:
        payload = run_url_intake_submit(
            db,
            raw_url=body.url,
            collection_id_param=body.collection_id,
            title=body.title,
        )
    except IntakeValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return UrlIntakeResponse(**payload)


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> DocumentDetailOut:
    """Single document with intake sources (locators, mime, sizes)."""
    out = get_document_for_user(db, document_id=document_id, auth_sub=user_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, sources = out
    base = DocumentSummaryOut.model_validate(doc)
    return DocumentDetailOut(
        **base.model_dump(),
        sources=[DocumentSourceOut.model_validate(s) for s in sources],
    )


@router.delete("/{document_id}", status_code=204)
def remove_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage_dep),
    user_id: str = Depends(get_current_user),
) -> Response:
    """Delete canonical row (cascades sources) and remove raw object from storage when possible."""
    ok = delete_document_for_user(
        db,
        document_id=document_id,
        auth_sub=user_id,
        storage=storage,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)


@router.post("", response_model=IntakeResponse)
def upload_document(
    file: UploadFile = File(..., description="Raw file bytes for intake"),
    collection_id: str | None = Form(
        default=None,
        description=(
            "Target collection UUID; defaults to VERIFIEDSIGNAL_DEFAULT_COLLECTION_ID when omitted"
        ),
    ),
    title: str | None = Form(
        default=None,
        description="Optional display title (defaults to filename)",
    ),
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage_dep),
    _user_id: str = Depends(get_current_user),
) -> IntakeResponse:
    """
    Phase 1 intake: validate, insert canonical `documents` row (`created`), upload to S3/MinIO,
    finalize to `queued` with `document_sources`, enqueue `process_document`.

    Sync handler so `asyncio.run` inside storage/queue helpers is safe (runs on a worker thread).
    """
    _ = _user_id
    raw = file.file.read()
    try:
        payload = run_file_intake(
            db,
            file_bytes=raw,
            original_filename=file.filename or "upload",
            content_type=file.content_type,
            title=title,
            collection_id_param=collection_id,
            storage=storage,
        )
    except IntakeValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except StorageUploadError as e:
        did = e.document_id
        raise HTTPException(
            status_code=502,
            detail={
                "message": "object storage upload failed",
                "error": str(e),
                "document_id": str(did) if did is not None else None,
            },
        ) from e

    return IntakeResponse(**payload)
