"""Unit tests: PDF/DOCX/plain routing in document_content_extract."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.services.document_content_extract import extract_document_text


def _ocr_settings(**overrides):
    base = dict(
        ocr_enabled=True,
        ocr_pdf_fallback=True,
        ocr_max_pdf_pages=25,
        ocr_langs="eng",
        tesseract_cmd=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.unit
def test_extract_plain_text_by_content_type():
    text, note, kind = extract_document_text(b"hello\n", "text/plain", "x.txt")
    assert text == "hello"
    assert note is None
    assert kind == "plain"


@pytest.mark.unit
def test_extract_pdf_by_application_pdf():
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "UniquePdfToken")
    c.save()
    pdf = buf.getvalue()
    text, note, kind = extract_document_text(pdf, "application/pdf", "doc.pdf")
    assert "UniquePdfToken" in text
    assert note is None
    assert kind == "pdf"


@pytest.mark.unit
def test_extract_docx_by_filename_suffix():
    from docx import Document

    buf = BytesIO()
    d = Document()
    d.add_paragraph("UniqueDocxLine")
    d.save(buf)
    docx = buf.getvalue()
    text, note, kind = extract_document_text(
        docx,
        "application/octet-stream",
        "report.docx",
    )
    assert "UniqueDocxLine" in text
    assert note is None
    assert kind == "docx"


@pytest.mark.unit
def test_extract_openapi_json_octet_stream_by_suffix():
    raw = b'{"openapi": "3.1.0", "info": {"title": "t"}}'
    text, note, kind = extract_document_text(
        raw,
        "application/octet-stream",
        "openapi.json",
    )
    assert "openapi" in text
    assert "3.1.0" in text
    assert note is None
    assert kind == "plain"


@pytest.mark.unit
def test_extract_openapi_yaml_octet_stream_by_suffix():
    raw = b"openapi: 3.0.0\ninfo:\n  title: Ref\n"
    text, note, kind = extract_document_text(
        raw,
        "application/octet-stream",
        "openapi.yaml",
    )
    assert "openapi" in text
    assert "Ref" in text
    assert note is None
    assert kind == "plain"


@pytest.mark.unit
def test_extract_markdown_octet_stream_by_suffix():
    raw = b"# Title\n\n- item\n"
    text, note, kind = extract_document_text(
        raw,
        "application/octet-stream",
        "README.md",
    )
    assert "# Title" in text
    assert note is None
    assert kind == "plain"


@pytest.mark.unit
def test_extract_python_and_javascript_octet_stream_by_suffix():
    for name, raw in (
        ("app.py", b"def hello():\n    return 1\n"),
        ("App.java", b"public class App { }\n"),
        ("app.js", b"export const x = 1;\n"),
    ):
        text, note, kind = extract_document_text(raw, "application/octet-stream", name)
        assert text.strip(), name
        assert note is None
        assert kind == "plain"


@pytest.mark.unit
def test_extract_binary_unknown():
    text, note, kind = extract_document_text(
        b"\x00\x01\xff\xfe",
        "application/octet-stream",
        "x.bin",
    )
    assert text == ""
    assert note == "binary_or_unsupported_content_type"
    assert kind == "unsupported"


@pytest.mark.unit
def test_extract_png_ocr_mocked():
    pytest.importorskip("PIL")
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (20, 20), color="white").save(buf, format="PNG")
    png = buf.getvalue()
    with patch("app.services.document_content_extract.get_settings", return_value=_ocr_settings()):
        with patch("pytesseract.image_to_string", return_value="ScannedLine\n"):
            text, note, kind = extract_document_text(png, "image/png", "memo.png")
    assert "ScannedLine" in text
    assert note is None
    assert kind == "ocr_image"


@pytest.mark.unit
def test_extract_png_octet_stream_by_suffix_ocr_mocked():
    pytest.importorskip("PIL")
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="PNG")
    png = buf.getvalue()
    with patch("app.services.document_content_extract.get_settings", return_value=_ocr_settings()):
        with patch("pytesseract.image_to_string", return_value="x\n"):
            text, note, kind = extract_document_text(
                png, "application/octet-stream", "photo.PNG"
            )
    assert text.strip() == "x"
    assert kind == "ocr_image"


@pytest.mark.unit
def test_extract_image_skips_ocr_when_disabled():
    pytest.importorskip("PIL")
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (8, 8), color="white").save(buf, format="PNG")
    png = buf.getvalue()
    with patch(
        "app.services.document_content_extract.get_settings",
        return_value=_ocr_settings(ocr_enabled=False),
    ):
        text, note, kind = extract_document_text(png, "image/png", "x.png")
    assert text == ""
    assert "unsupported" in (note or "") or note == "binary_or_unsupported_content_type"
    assert kind == "unsupported"


@pytest.mark.unit
def test_extract_pdf_ocr_fallback_mocked():
    with patch(
        "app.services.document_content_extract._extract_pdf",
        return_value=("", None),
    ), patch(
        "app.services.document_content_extract._extract_pdf_pages_ocr",
        return_value=("FallbackOcr", None),
    ), patch(
        "app.services.document_content_extract.get_settings",
        return_value=_ocr_settings(),
    ):
        text, note, kind = extract_document_text(b"%PDF-1.4\n", "application/pdf", "scan.pdf")
    assert "FallbackOcr" in text
    assert note is None
    assert kind == "ocr_pdf"
