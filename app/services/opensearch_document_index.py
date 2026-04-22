"""
OpenSearch index for documents (text + metadata keyword fields). In-memory fake for tests.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.search_filters import (
    SearchFilters,
    fake_doc_matches_filters,
    opensearch_filter_clauses,
)
from app.services.text_embedding_stub import cosine_similarity, deterministic_text_embedding

log = logging.getLogger("verifiedsignal.opensearch")

_EMBED_DIM = 64

_fake_lock = threading.Lock()
_fake_docs: dict[str, dict[str, Any]] = {}


def reset_fake_opensearch_index() -> None:
    """Test hook: clear in-memory index."""
    with _fake_lock:
        _fake_docs.clear()


def _index_url(settings: Settings) -> str:
    base = settings.opensearch_url.rstrip("/")
    name = settings.opensearch_index_name.strip() or "verifiedsignal_documents"
    return f"{base}/{name}"


def _base_mapping_properties() -> dict[str, Any]:
    return {
        "document_id": {"type": "keyword"},
        "collection_id": {"type": "keyword"},
        "title": {"type": "text"},
        "body_text": {"type": "text"},
        "status": {"type": "keyword"},
        "content_type": {"type": "keyword"},
        "original_filename": {"type": "keyword"},
        "ingest_source": {"type": "keyword"},
        "tags": {"type": "keyword"},
        "metadata_label": {"type": "keyword"},
        "metadata_text": {"type": "text"},
        "embedding": {
            "type": "knn_vector",
            "dimension": _EMBED_DIM,
            "method": {
                "name": "hnsw",
                "space_type": "innerproduct",
                "engine": "lucene",
            },
        },
    }


def ensure_index_and_mapping(settings: Settings | None = None) -> None:
    """Create index with mapping if missing; merge new properties on existing index (no-op fake)."""
    settings = settings or get_settings()
    if settings.use_fake_opensearch:
        return

    base = settings.opensearch_url.rstrip("/")
    name = settings.opensearch_index_name.strip() or "verifiedsignal_documents"
    create_body = {
        "settings": {"index": {"knn": True}},
        "mappings": {"properties": _base_mapping_properties()},
    }
    url = f"{base}/{name}"
    with httpx.Client(timeout=30.0) as client:
        r = client.put(url, json=create_body)
        if r.status_code in (200, 201):
            return
        try:
            body = r.json()
        except Exception:
            body = {}
        err = body.get("error", {})
        if r.status_code == 400 and err.get("type") == "resource_already_exists_exception":
            pass
        else:
            log.warning(
                "opensearch_create_index_failed status=%s body=%s",
                r.status_code,
                r.text[:500],
            )
            return
        mr = client.put(f"{url}/_mapping", json={"properties": _base_mapping_properties()})
        if mr.status_code not in (200,):
            log.debug("opensearch_merge_mapping status=%s text=%s", mr.status_code, mr.text[:300])


def index_document_sync(
    *,
    document_id: uuid.UUID,
    collection_id: uuid.UUID,
    title: str | None,
    body_text: str | None,
    status: str,
    settings: Settings | None = None,
    content_type: str | None = None,
    original_filename: str | None = None,
    ingest_source: str = "upload",
    tags: list[str] | None = None,
    metadata_label: str | None = None,
    metadata_text: str = "",
    embedding: list[float] | None = None,
) -> None:
    settings = settings or get_settings()
    doc_id = str(document_id)
    tag_list = tags or []
    embed = embedding
    if embed is None:
        embed_text = " ".join(x for x in (title or "", (body_text or "")[:12000]) if x)
        embed = deterministic_text_embedding(embed_text, dim=_EMBED_DIM)
    payload: dict[str, Any] = {
        "document_id": doc_id,
        "collection_id": str(collection_id),
        "title": title or "",
        "body_text": body_text or "",
        "status": status,
        "content_type": content_type or "",
        "original_filename": original_filename or "",
        "ingest_source": ingest_source,
        "tags": tag_list,
        "metadata_label": metadata_label or "",
        "metadata_text": metadata_text or "",
    }
    if settings.use_fake_opensearch or settings.opensearch_index_embeddings:
        payload["embedding"] = embed
    if settings.use_fake_opensearch:
        with _fake_lock:
            _fake_docs[doc_id] = payload
        return

    ensure_index_and_mapping(settings)
    url = f"{_index_url(settings)}/_doc/{doc_id}?refresh=wait_for"
    with httpx.Client(timeout=30.0) as client:
        r = client.put(url, json=payload)
        if r.status_code in (200, 201):
            return
        if settings.opensearch_index_embeddings and "embedding" in payload:
            slim = {k: v for k, v in payload.items() if k != "embedding"}
            r2 = client.put(url, json=slim)
            if r2.status_code in (200, 201):
                return
            log.warning(
                "opensearch_index_failed document_id=%s status=%s text=%s",
                doc_id,
                r2.status_code,
                r2.text[:500],
            )
        else:
            log.warning(
                "opensearch_index_failed document_id=%s status=%s text=%s",
                doc_id,
                r.status_code,
                r.text[:500],
            )


def delete_document_from_index_sync(
    document_id: uuid.UUID,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    doc_id = str(document_id)
    if settings.use_fake_opensearch:
        with _fake_lock:
            _fake_docs.pop(doc_id, None)
        return

    url = f"{_index_url(settings)}/_doc/{doc_id}?refresh=wait_for"
    with httpx.Client(timeout=30.0) as client:
        r = client.delete(url)
        if r.status_code not in (200, 404):
            log.debug(
                "opensearch_delete_unexpected document_id=%s status=%s",
                doc_id,
                r.status_code,
            )


def _bool_query_text(q: str) -> dict[str, Any]:
    q = (q or "").strip()
    if q:
        return {
            "multi_match": {
                "query": q,
                "fields": ["title^2", "body_text", "metadata_text"],
                "type": "best_fields",
            }
        }
    return {"match_all": {}}


def _rerank_opensearch_hits(
    raw_hits: list[dict[str, Any]],
    query: str,
    limit: int,
    semantic_weight: float,
) -> list[dict[str, Any]]:
    w = max(0.0, min(1.0, semantic_weight))
    q = (query or "").strip()
    if w <= 0 or not q:
        return raw_hits[:limit]
    q_emb = deterministic_text_embedding(q, dim=_EMBED_DIM)
    max_ts = max((float(h.get("_score") or 0.0) for h in raw_hits), default=1.0) or 1.0
    scored: list[tuple[float, dict[str, Any]]] = []
    for h in raw_hits:
        ts = float(h.get("_score") or 0.0) / max_ts
        src = h.get("_source") or {}
        emb = src.get("embedding")
        if isinstance(emb, list) and len(emb) == _EMBED_DIM:
            cos = max(0.0, cosine_similarity(q_emb, [float(x) for x in emb]))
        else:
            cos = 0.0
        combined = (1.0 - w) * ts + w * cos
        scored.append((combined, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored[:limit]]


def search_documents_sync(
    query: str,
    *,
    limit: int,
    filters: SearchFilters,
    include_facets: bool = False,
    settings: Settings | None = None,
    semantic_weight: float = 0.0,
) -> dict[str, Any]:
    """
    Full-text + metadata filters; optional facet aggregations on source, status, type, tags.
    """
    settings = settings or get_settings()
    lim = max(1, min(limit, 100))

    if settings.use_fake_opensearch:
        return _search_fake(query, lim, filters, include_facets, semantic_weight)

    ensure_index_and_mapping(settings)
    fclauses = opensearch_filter_clauses(filters)
    must = _bool_query_text(query)
    bool_q: dict[str, Any] = {"must": [must]}
    if fclauses:
        bool_q["filter"] = fclauses
    fetch_lim = lim
    w = max(0.0, min(1.0, semantic_weight))
    if w > 0 and (query or "").strip():
        fetch_lim = min(100, max(lim * 4, lim))
    body: dict[str, Any] = {
        "size": fetch_lim,
        "track_total_hits": True,
        "query": {"bool": bool_q},
    }
    if include_facets:
        body["aggs"] = {
            "ingest_source": {"terms": {"field": "ingest_source", "size": 10}},
            "status": {"terms": {"field": "status", "size": 20}},
            "content_type": {"terms": {"field": "content_type", "size": 30}},
            "tags": {"terms": {"field": "tags", "size": 50}},
        }

    url = f"{_index_url(settings)}/_search"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=body)
        if r.status_code != 200:
            return {
                "hits": [],
                "total": 0,
                "index_status": "error",
                "message": f"OpenSearch HTTP {r.status_code}: {r.text[:300]}",
                "facets": None,
            }
        data = r.json()
    raw_hits = list(data.get("hits", {}).get("hits", []))
    ranked_hits = _rerank_opensearch_hits(raw_hits, query, lim, semantic_weight)
    hits_out: list[dict[str, Any]] = []
    for h in ranked_hits:
        src = h.get("_source") or {}
        hits_out.append(
            {
                "document_id": src.get("document_id"),
                "title": src.get("title"),
                "score": h.get("_score"),
                "snippet": (src.get("body_text") or "")[:280],
                "collection_id": src.get("collection_id"),
                "ingest_source": src.get("ingest_source"),
                "content_type": src.get("content_type"),
                "status": src.get("status"),
                "tags": src.get("tags") or [],
                "metadata_label": src.get("metadata_label") or None,
            }
        )
    total = data.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        total_val = int(total.get("value", 0))
    else:
        total_val = int(total or 0)

    facets_out: dict[str, Any] | None = None
    if include_facets and "aggregations" in data:
        facets_out = {}
        for key, spec in data["aggregations"].items():
            buckets = spec.get("buckets", [])
            facets_out[key] = [
                {"key": b.get("key"), "count": b.get("doc_count", 0)}
                for b in buckets
            ]

    return {
        "hits": hits_out,
        "total": total_val,
        "index_status": "ok",
        "message": None,
        "facets": facets_out,
    }


def facet_aggregation_sync(
    *,
    filters: SearchFilters,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    OpenSearch (or fake) facet buckets for filtered documents; uses minimal `size` for hits.
    """
    settings = settings or get_settings()
    out = search_documents_sync(
        "",
        limit=1,
        filters=filters,
        include_facets=True,
        settings=settings,
    )
    return {
        "total": out["total"],
        "index_status": out["index_status"],
        "message": out.get("message"),
        "facets": out.get("facets"),
    }


def search_keyword_sync(
    query: str,
    *,
    limit: int,
    settings: Settings | None = None,
    semantic_weight: float = 0.0,
) -> dict[str, Any]:
    """Backward-compatible: text search without metadata filters or facets."""
    out = search_documents_sync(
        query,
        limit=limit,
        filters=SearchFilters(),
        include_facets=False,
        settings=settings,
        semantic_weight=semantic_weight,
    )
    out.pop("facets", None)
    return out


def _search_fake(
    query: str,
    limit: int,
    filters: SearchFilters,
    include_facets: bool,
    semantic_weight: float = 0.0,
) -> dict[str, Any]:
    q_raw = (query or "").strip()
    q = q_raw.lower()
    with _fake_lock:
        docs = list(_fake_docs.values())
    filtered = [d for d in docs if fake_doc_matches_filters(d, filters)]
    if not q:
        text_matched = filtered
    else:
        text_matched = []
        for d in filtered:
            title = (d.get("title") or "").lower()
            body = (d.get("body_text") or "").lower()
            meta = (d.get("metadata_text") or "").lower()
            if q in title or q in body or q in meta:
                text_matched.append(d)
    w = max(0.0, min(1.0, semantic_weight))
    ranked = text_matched
    if w > 0 and q_raw:
        q_emb = deterministic_text_embedding(q_raw, dim=_EMBED_DIM)
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in ranked:
            title = (d.get("title") or "").lower()
            body = (d.get("body_text") or "").lower()
            meta = (d.get("metadata_text") or "").lower()
            kw = (
                1.0
                if (not q or q in title or q in body or q in meta)
                else 0.35
            )
            emb = d.get("embedding")
            if isinstance(emb, list) and len(emb) == _EMBED_DIM:
                cos = max(0.0, cosine_similarity(q_emb, [float(x) for x in emb]))
            else:
                cos = 0.0
            combined = (1.0 - w) * kw + w * cos
            scored.append((combined, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        ranked = [d for _, d in scored]
    ranked = ranked[:limit]
    hits = [
        {
            "document_id": d.get("document_id"),
            "title": d.get("title"),
            "score": 1.0,
            "snippet": (d.get("body_text") or "")[:280],
            "collection_id": d.get("collection_id"),
            "ingest_source": d.get("ingest_source"),
            "content_type": d.get("content_type"),
            "status": d.get("status"),
            "tags": d.get("tags") or [],
            "metadata_label": (d.get("metadata_label") or None) or None,
        }
        for d in ranked
    ]
    facets_out: dict[str, Any] | None = None
    if include_facets:
        facets_out = {
            "ingest_source": _facet_counts(text_matched, "ingest_source"),
            "status": _facet_counts(text_matched, "status"),
            "content_type": _facet_counts(text_matched, "content_type"),
            "tags": _facet_tag_counts(text_matched),
        }
    return {
        "hits": hits,
        "total": len(text_matched),
        "index_status": "fake",
        "message": None,
        "facets": facets_out,
    }


def _facet_counts(docs: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    c: Counter[str] = Counter()
    for d in docs:
        v = d.get(field)
        if v is None or v == "":
            continue
        c[str(v)] += 1
    return [{"key": k, "count": n} for k, n in c.most_common(50)]


def _facet_tag_counts(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    c: Counter[str] = Counter()
    for d in docs:
        tags = d.get("tags") or []
        if not isinstance(tags, list):
            continue
        for t in tags:
            if t:
                c[str(t)] += 1
    return [{"key": k, "count": n} for k, n in c.most_common(50)]
