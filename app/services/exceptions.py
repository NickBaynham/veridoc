"""Domain errors for intake and storage."""

from __future__ import annotations

import uuid


class IntakeValidationError(ValueError):
    """Invalid client input (filename, size, collection, etc.)."""


class StorageUploadError(Exception):
    """Object storage upload failed after canonical metadata may exist."""

    def __init__(self, message: str, *, document_id: uuid.UUID | None = None) -> None:
        super().__init__(message)
        self.document_id: uuid.UUID | None = document_id


class CollectionAccessError(Exception):
    """Caller cannot view or mutate this collection."""

    def __init__(self, message: str = "Collection not found") -> None:
        super().__init__(message)


class CollectionOrgAccessError(Exception):
    """Caller cannot create collections in the target organization."""

    def __init__(self, message: str = "Not allowed to create collections here") -> None:
        super().__init__(message)
