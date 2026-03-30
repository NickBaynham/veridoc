"""Unit tests: PDF/DOCX/plain routing in document_content_extract."""

from __future__ import annotations

from io import BytesIO

import pytest
from app.services.document_content_extract import extract_document_text


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
def test_extract_binary_unknown():
    text, note, kind = extract_document_text(
        b"\x00\x01\xff\xfe",
        "application/octet-stream",
        "x.bin",
    )
    assert text == ""
    assert note == "binary_or_unsupported_content_type"
    assert kind == "unsupported"
