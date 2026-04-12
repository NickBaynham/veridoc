"""Unit: intake row creation accepts folder-style titles (slashes in display title)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from app.repositories.document_repository import create_intake_row_created


@pytest.mark.unit
def test_create_intake_row_created_preserves_slash_title() -> None:
    session = MagicMock()
    cid = uuid.UUID("00000000-0000-4000-8000-000000000002")
    did = uuid.uuid4()
    doc = create_intake_row_created(
        session,
        document_id=did,
        collection_id=cid,
        original_filename="readme.txt",
        content_type="text/plain",
        file_size=12,
        title="corp/handbook/sections/readme.txt",
    )
    assert doc.title == "corp/handbook/sections/readme.txt"
    session.add.assert_called_once()
    session.flush.assert_called_once()
