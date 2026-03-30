"""
Extract searchable plain text from uploaded bytes (PDF, DOCX, text-like types).

Used by the worker extract stage; keeps routing separate from storage I/O.
"""

from __future__ import annotations

import logging
from io import BytesIO

from app.services.document_text_extract import extract_plain_text_from_bytes

log = logging.getLogger("verifiedsignal.document_content_extract")


def _suffix(name: str | None) -> str:
    if not name:
        return ""
    n = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    if "." not in n:
        return ""
    return "." + n.rsplit(".", 1)[-1]


def _extract_pdf(data: bytes) -> tuple[str, str | None]:
    try:
        from pypdf import PasswordType, PdfReader
    except ImportError as e:  # pragma: no cover
        return "", f"pdf_import:{e}"

    try:
        reader = PdfReader(BytesIO(data))
        if getattr(reader, "is_encrypted", False):
            empty = ""
            try:
                if reader.decrypt(empty) == PasswordType.NOT_DECRYPTED:
                    return "", "pdf_encrypted"
            except Exception:
                return "", "pdf_encrypted"
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
        return "\n".join(parts).strip(), None
    except Exception as e:
        log.debug("pdf_extract_failed err=%s", e)
        return "", f"pdf_error:{type(e).__name__}"


def _extract_docx(data: bytes) -> tuple[str, str | None]:
    try:
        from docx import Document
    except ImportError as e:  # pragma: no cover
        return "", f"docx_import:{e}"

    try:
        doc = Document(BytesIO(data))
        lines = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n".join(lines).strip(), None
    except Exception as e:
        log.debug("docx_extract_failed err=%s", e)
        return "", f"docx_error:{type(e).__name__}"


def extract_document_text(
    data: bytes,
    content_type: str | None,
    original_filename: str | None,
) -> tuple[str, str | None, str]:
    """
    Return (text, error_or_skip_note, kind).

    ``kind`` is one of: pdf, docx, plain, utf8_heuristic, empty, unsupported.
    """
    if not data:
        return "", "empty_bytes", "empty"

    ct = (content_type or "").split(";")[0].strip().lower()
    suf = _suffix(original_filename)

    if ct == "application/pdf" or suf == ".pdf":
        text, err = _extract_pdf(data)
        if err:
            return "", err, "pdf"
        return text, None if text else "pdf_no_text", "pdf"

    if (
        ct == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or suf == ".docx"
    ):
        text, err = _extract_docx(data)
        if err:
            return "", err, "docx"
        return text, None if text else "docx_no_text", "docx"

    text, note = extract_plain_text_from_bytes(data, content_type)
    if text:
        return text, note, "plain" if note is None else "utf8_heuristic"
    return "", note or "unsupported", "unsupported"
