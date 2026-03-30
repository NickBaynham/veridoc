"""
Decode stored raw bytes into plain text for keyword search (minimal extract path).

Supports common text-like types and a UTF-8 heuristic for small payloads.
"""

from __future__ import annotations

import re
from typing import Final

# Keep bounded for Postgres TEXT + OpenSearch; tunable via constant.
MAX_BODY_TEXT_CHARS: Final[int] = 1_000_000

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _truncate(text: str, max_chars: int = MAX_BODY_TEXT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def truncate_for_body(text: str, max_chars: int = MAX_BODY_TEXT_CHARS) -> str:
    """Bound Postgres `documents.body_text` / OpenSearch field size."""
    return _truncate(text, max_chars)


def _strip_html_loose(html: str) -> str:
    text = _HTML_TAG_RE.sub(" ", html)
    return " ".join(text.split())


def _looks_like_utf8_text(data: bytes, *, max_scan: int = 8192) -> bool:
    if not data or len(data) > 5_000_000:
        return False
    sample = data[:max_scan]
    text_bytes = sum(32 <= b < 127 or b in (9, 10, 13) for b in sample)
    return text_bytes / max(len(sample), 1) >= 0.85


def extract_plain_text_from_bytes(
    data: bytes,
    content_type: str | None,
) -> tuple[str, str | None]:
    """
    Return (text, skip_reason). skip_reason is set when we intentionally store no text.
    """
    if not data:
        return "", "empty_bytes"

    ct = (content_type or "").split(";")[0].strip().lower()

    text_like = (
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/xml",
        "text/xml",
        "text/html",
    )
    if ct in text_like or ct.startswith("text/"):
        raw = data.decode("utf-8", errors="replace")
        raw = _CONTROL_RE.sub("", raw)
        if ct == "text/html" or ct.endswith("+html"):
            raw = _strip_html_loose(raw)
        return _truncate(raw.strip()), None

    if _looks_like_utf8_text(data):
        raw = data.decode("utf-8", errors="replace")
        raw = _CONTROL_RE.sub("", raw)
        return _truncate(raw.strip()), None

    return "", "binary_or_unsupported_content_type"
