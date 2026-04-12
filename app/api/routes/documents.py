"""Document intake: multipart upload, canonical Postgres row, storage, enqueue."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_object_storage_dep
from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models import DocumentScore
from app.rate_limit import limiter
from app.schemas.document import (
    CanonicalScoreOut,
    DocumentCollectionTargetIn,
    DocumentDetailOut,
    DocumentListResponse,
    DocumentSourceOut,
    DocumentSummaryOut,
    IntakeResponse,
    UrlIntakeRequest,
    UrlIntakeResponse,
)
from app.schemas.pipeline import DocumentPipelineOut
from app.services.document_service import (
    delete_document_for_user,
    get_document_for_user,
    list_documents_for_user,
    run_file_intake,
    run_url_intake_submit,
)
from app.services.document_transfer_service import (
    copy_document_for_user,
    move_document_for_user,
)
from app.services.exceptions import (
    IntakeValidationError,
    StorageUploadError,
    TargetCollectionAccessError,
)
from app.services.pipeline_status_service import get_document_pipeline_for_user
from app.services.storage_service import ObjectStorage
from app.services.user_metadata import parse_metadata_json_string, validate_user_metadata

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
@limiter.limit(lambda: get_settings().rate_limit_documents_intake)
def ingest_document_from_url(
    request: Request,
    body: UrlIntakeRequest,
    db: Session = Depends(get_db),
    _user_id: str = Depends(get_current_user),
) -> UrlIntakeResponse:
    """
    Accept a remote URL: `created` row + `url` source, then worker fetch → S3 → pipeline.

    Poll `GET /documents/{id}` for `queued` / `failed` after the fetch job completes.
    """
    _ = _user_id
    _ = request  # required by slowapi rate limit; marks dependency for linters
    try:
        payload = run_url_intake_submit(
            db,
            raw_url=body.url,
            collection_id_param=body.collection_id,
            title=body.title,
            user_metadata=body.metadata,
        )
    except IntakeValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return UrlIntakeResponse(**payload)


@router.get("/{document_id}/pipeline", response_model=DocumentPipelineOut)
def get_document_pipeline(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> DocumentPipelineOut:
    """Latest pipeline run and events for polling + UI progress (worker writes to Postgres)."""
    out = get_document_pipeline_for_user(db, document_id=document_id, auth_sub=user_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return out


@router.post("/{document_id}/move", response_model=DocumentSummaryOut)
def move_document_to_collection(
    document_id: uuid.UUID,
    body: DocumentCollectionTargetIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> DocumentSummaryOut:
    """Set the document's collection when both collections are visible to the caller."""
    try:
        doc = move_document_for_user(
            db,
            user_id,
            document_id=document_id,
            target_collection_id=body.collection_id,
        )
    except IntakeValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TargetCollectionAccessError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentSummaryOut.model_validate(doc)


@router.post("/{document_id}/copy", response_model=DocumentSummaryOut, status_code=201)
def copy_document_to_collection(
    document_id: uuid.UUID,
    body: DocumentCollectionTargetIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user),
) -> DocumentSummaryOut:
    """
    Duplicate the document row (and sources + scores) into another collection.

    Raw and extract object keys are reused until all rows referencing them are deleted.
    """
    try:
        doc = copy_document_for_user(
            db,
            user_id,
            document_id=document_id,
            target_collection_id=body.collection_id,
        )
    except TargetCollectionAccessError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentSummaryOut.model_validate(doc)


def _content_disposition_attachment(filename: str) -> str:
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii").strip() or "download.bin"
    ascii_fallback = ascii_fallback.replace('"', "").replace("\\", "")
    utf8_quoted = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8_quoted}"


@router.get(
    "/{document_id}/file",
    response_model=None,
    responses={
        302: {"description": "Redirect to a short-lived presigned object URL (when supported)."},
        404: {"description": "Document not found, no original on file, or object missing."},
        502: {"description": "Storage read failure when streaming the body."},
    },
)
def download_document_original(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: ObjectStorage = Depends(get_object_storage_dep),
    _user_id: str = Depends(get_current_user),
    redirect: Annotated[
        bool,
        Query(
            description=(
                "When true (default), return 302 to a presigned GET URL if the storage backend "
                "supports signing. Otherwise stream bytes through this API "
                "(still requires Bearer auth)."
            ),
        ),
    ] = True,
) -> Response | RedirectResponse:
    """
    Download the stored original bytes (same access rules as GET /documents/{id}).

    With real S3/MinIO, **redirect=true** avoids proxying large files through the API. Clients that
    cannot follow redirects to the object host (or need a single authenticated hop) should use
    **redirect=false**.
    """
    settings = get_settings()
    out = get_document_for_user(db, document_id=document_id, auth_sub=_user_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, _sources = out
    if not doc.storage_key:
        raise HTTPException(
            status_code=404,
            detail="Original file is not available for this document",
        )
    if not storage.object_exists(doc.storage_key):
        raise HTTPException(
            status_code=404,
            detail="Original file is missing from object storage",
        )

    filename = doc.original_filename or doc.storage_key.rsplit("/", 1)[-1]
    media_type = doc.content_type or "application/octet-stream"

    if redirect:
        signed = storage.presigned_get_url(
            doc.storage_key,
            expires_seconds=settings.download_presigned_ttl_seconds,
        )
        if signed:
            return RedirectResponse(url=signed, status_code=302)

    try:
        body = storage.get_bytes(doc.storage_key)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Original file is missing from object storage",
        ) from None
    except StorageUploadError as e:
        raise HTTPException(
            status_code=502,
            detail={"message": "failed to read object from storage", "error": str(e)},
        ) from e

    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )


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
    score_row = db.scalar(
        select(DocumentScore)
        .where(
            DocumentScore.document_id == doc.id,
            DocumentScore.is_canonical.is_(True),
        )
        .limit(1)
    )
    canon: CanonicalScoreOut | None = None
    if score_row is not None:
        canon = CanonicalScoreOut(
            factuality_score=float(score_row.factuality_score)
            if score_row.factuality_score is not None
            else None,
            ai_generation_probability=float(score_row.ai_generation_probability)
            if score_row.ai_generation_probability is not None
            else None,
            fallacy_score=float(score_row.fallacy_score)
            if score_row.fallacy_score is not None
            else None,
            confidence_score=float(score_row.confidence_score)
            if score_row.confidence_score is not None
            else None,
            scorer_name=score_row.scorer_name,
            scorer_version=score_row.scorer_version,
        )
    return DocumentDetailOut(
        **base.model_dump(),
        sources=[DocumentSourceOut.model_validate(s) for s in sources],
        body_text=doc.body_text,
        canonical_score=canon,
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
@limiter.limit(lambda: get_settings().rate_limit_documents_intake)
def upload_document(
    request: Request,
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
    metadata: str | None = Form(
        default=None,
        description='Optional JSON object, e.g. {"tags":["finance"],"label":"report"}',
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
    _ = request
    raw = file.file.read()
    try:
        um = validate_user_metadata(parse_metadata_json_string(metadata))
        payload = run_file_intake(
            db,
            file_bytes=raw,
            original_filename=file.filename or "upload",
            content_type=file.content_type,
            title=title,
            collection_id_param=collection_id,
            user_metadata=um,
            storage=storage,
            auth_sub=_user_id,
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
