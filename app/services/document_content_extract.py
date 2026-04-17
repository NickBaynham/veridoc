"""
Extract searchable plain text from uploaded bytes (PDF, DOCX, text-like types, OCR).

Used by the worker extract stage; keeps routing separate from storage I/O.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from io import BytesIO
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.services.document_text_extract import extract_plain_text_from_bytes

if TYPE_CHECKING:
    from app.core.config import Settings

log = logging.getLogger("verifiedsignal.document_content_extract")

# Filename → synthetic Content-Type for UTF-8 decode when browsers send
# `application/octet-stream` (same problem as OpenAPI `.json` / `.yaml`).
_TEXT_LIKE_SUFFIXES: dict[str, str] = {
    # Markdown & plain text
    ".md": "text/plain",
    ".markdown": "text/plain",
    ".txt": "text/plain",
    ".text": "text/plain",
    ".log": "text/plain",
    # CSV / markup
    ".csv": "text/csv",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
    # OpenAPI / config
    ".json": "application/json",
    ".yaml": "text/plain",
    ".yml": "text/plain",
    # JavaScript / TypeScript
    ".js": "text/plain",
    ".mjs": "text/plain",
    ".cjs": "text/plain",
    ".jsx": "text/plain",
    ".ts": "text/plain",
    ".tsx": "text/plain",
    # JVM / Python
    ".java": "text/plain",
    ".py": "text/plain",
    ".pyw": "text/plain",
    ".pyi": "text/plain",
}

_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".tif",
        ".tiff",
        ".bmp",
    }
)


def _suffix(name: str | None) -> str:
    if not name:
        return ""
    n = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    if "." not in n:
        return ""
    return "." + n.rsplit(".", 1)[-1]


def _is_image_type(content_type: str, suf: str) -> bool:
    ct = (content_type or "").split(";")[0].strip().lower()
    return ct.startswith("image/") or suf in _IMAGE_SUFFIXES


@contextmanager
def _tesseract_cmd_context(cmd: str | None):
    import pytesseract

    prev = pytesseract.pytesseract.tesseract_cmd
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        yield
    finally:
        pytesseract.pytesseract.tesseract_cmd = prev


def _prepare_pil_image(im):  # PIL.Image.Image
    if im.mode not in ("RGB", "L"):
        return im.convert("RGB")
    return im


def _extract_image_ocr(data: bytes, settings: Settings) -> tuple[str, str | None]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        return "", f"ocr_import:{e}"

    try:
        im = Image.open(BytesIO(data))
        im = _prepare_pil_image(im)
        lang = (settings.ocr_langs or "eng").strip() or "eng"
        with _tesseract_cmd_context(
            (settings.tesseract_cmd or "").strip() or None
        ):
            text = pytesseract.image_to_string(im, lang=lang)
        return text.strip(), None
    except Exception as e:
        log.debug("ocr_image_failed err=%s", e)
        return "", f"ocr_error:{type(e).__name__}"


def _extract_pdf_pages_ocr(data: bytes, settings: Settings) -> tuple[str, str | None]:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError as e:  # pragma: no cover
        return "", f"ocr_pdf_import:{e}"

    try:
        pages = convert_from_bytes(
            data,
            dpi=150,
            fmt="png",
            last_page=settings.ocr_max_pdf_pages,
        )
    except Exception as e:
        log.debug("ocr_pdf_render_failed err=%s", e)
        return "", f"ocr_pdf_render:{type(e).__name__}"

    lang = (settings.ocr_langs or "eng").strip() or "eng"
    parts: list[str] = []
    try:
        with _tesseract_cmd_context(
            (settings.tesseract_cmd or "").strip() or None
        ):
            for page_im in pages:
                page_im = _prepare_pil_image(page_im)
                t = pytesseract.image_to_string(page_im, lang=lang)
                if t.strip():
                    parts.append(t.strip())
    except Exception as e:
        log.debug("ocr_pdf_tesseract_failed err=%s", e)
        return "", f"ocr_error:{type(e).__name__}"

    return "\n".join(parts).strip(), None


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

    ``kind`` is one of: pdf, docx, plain, utf8_heuristic, ocr_image, ocr_pdf,
    empty, unsupported.
    """
    if not data:
        return "", "empty_bytes", "empty"

    ct = (content_type or "").split(";")[0].strip().lower()
    suf = _suffix(original_filename)
    settings = get_settings()

    if ct == "application/pdf" or suf == ".pdf":
        text, err = _extract_pdf(data)
        if err:
            return "", err, "pdf"
        if text.strip():
            return text, None, "pdf"
        if settings.ocr_enabled and settings.ocr_pdf_fallback:
            ocr_text, ocr_note = _extract_pdf_pages_ocr(data, settings)
            if ocr_text:
                return ocr_text, ocr_note, "ocr_pdf"
            if ocr_note:
                return "", f"pdf_no_text:{ocr_note}", "pdf"
        return "", "pdf_no_text", "pdf"

    if (
        ct == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or suf == ".docx"
    ):
        text, err = _extract_docx(data)
        if err:
            return "", err, "docx"
        return text, None if text else "docx_no_text", "docx"

    if _is_image_type(ct, suf):
        if not settings.ocr_enabled:
            text, note = extract_plain_text_from_bytes(data, content_type)
            if text:
                return text, note, "plain" if note is None else "utf8_heuristic"
            return "", note or "unsupported", "unsupported"
        ocr_text, ocr_note = _extract_image_ocr(data, settings)
        if ocr_text:
            return ocr_text, ocr_note, "ocr_image"
        return "", ocr_note or "ocr_no_text", "ocr_image"

    if suf in _TEXT_LIKE_SUFFIXES:
        text, note = extract_plain_text_from_bytes(data, _TEXT_LIKE_SUFFIXES[suf])
        if text:
            return text, note, "plain" if note is None else "utf8_heuristic"
        return "", note or "text_suffix_decode_empty", "unsupported"

    text, note = extract_plain_text_from_bytes(data, content_type)
    if text:
        return text, note, "plain" if note is None else "utf8_heuristic"
    return "", note or "unsupported", "unsupported"
