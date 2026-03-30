"""
S3-compatible object storage (MinIO locally, AWS S3 in production).

Uses boto3 with path-style addressing for MinIO compatibility.
"""

from __future__ import annotations

import re
import uuid
from typing import IO, Protocol, runtime_checkable

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.services.exceptions import StorageUploadError


def sanitize_filename(name: str, *, max_length: int = 200) -> str:
    """
    Produce a single path segment safe for object keys (no slashes, no traversal).
    """
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = base.strip() or "unnamed"
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", base)
    if len(base) > max_length:
        root, dot, ext = base.rpartition(".")
        if dot and len(ext) <= 10:
            base = (root[: max_length - len(ext) - 1] + "." + ext)[:max_length]
        else:
            base = base[:max_length]
    return base


def build_raw_object_key(document_id: uuid.UUID, original_filename: str) -> str:
    """Deterministic key: raw/{document_id}/{safe_filename}."""
    safe = sanitize_filename(original_filename)
    return f"raw/{document_id}/{safe}"


def build_extract_artifact_key(document_id: uuid.UUID) -> str:
    """Deterministic key for pipeline-extracted UTF-8 text."""
    return f"artifacts/{document_id}/extracted.txt"


@runtime_checkable
class ObjectStorage(Protocol):
    """Swappable storage backend (MinIO / S3 / fakes)."""

    @property
    def bucket(self) -> str: ...

    def ensure_bucket(self) -> None: ...

    def upload_bytes(self, key: str, body: bytes, content_type: str | None) -> None: ...

    def upload_fileobj(self, key: str, fileobj: IO[bytes], content_type: str | None) -> None: ...

    def delete_object(self, key: str) -> None: ...

    def object_exists(self, key: str) -> bool: ...

    def get_bytes(self, key: str) -> bytes: ...


class InMemoryObjectStorage:
    """Test / local dev without MinIO."""

    def __init__(self, bucket: str = "verifiedsignal") -> None:
        self._bucket = bucket
        self.objects: dict[str, bytes] = {}

    @property
    def bucket(self) -> str:
        return self._bucket

    def ensure_bucket(self) -> None:
        return

    def upload_bytes(self, key: str, body: bytes, content_type: str | None) -> None:
        _ = content_type
        self.objects[key] = body

    def upload_fileobj(self, key: str, fileobj: IO[bytes], content_type: str | None) -> None:
        self.upload_bytes(key, fileobj.read(), content_type)

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)

    def object_exists(self, key: str) -> bool:
        return key in self.objects

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key]


class S3ObjectStorage:
    """boto3 S3 client with optional custom endpoint (MinIO)."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        use_path_style: bool,
    ) -> None:
        self._bucket = bucket
        cfg = Config(
            s3={"addressing_style": "path" if use_path_style else "auto"},
            signature_version="s3v4",
        )
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=cfg,
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchBucket", "NotFound"):
                try:
                    self._client.create_bucket(Bucket=self._bucket)
                except (ClientError, BotoCoreError) as create_exc:
                    raise StorageUploadError(
                        f"cannot create bucket {self._bucket}: {create_exc}"
                    ) from create_exc
            else:
                raise StorageUploadError(f"bucket check failed: {e}") from e
        except BotoCoreError as e:
            raise StorageUploadError(str(e)) from e

    def upload_bytes(self, key: str, body: bytes, content_type: str | None) -> None:
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=body, **extra)
        except (ClientError, BotoCoreError) as e:
            raise StorageUploadError(str(e)) from e

    def upload_fileobj(self, key: str, fileobj: IO[bytes], content_type: str | None) -> None:
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type
        try:
            self._client.upload_fileobj(fileobj, self._bucket, key, ExtraArgs=extra)
        except (ClientError, BotoCoreError) as e:
            raise StorageUploadError(str(e)) from e

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return
            raise StorageUploadError(f"delete object failed: {e}") from e
        except BotoCoreError as e:
            raise StorageUploadError(str(e)) from e

    def object_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StorageUploadError(f"head object failed: {e}") from e
        except BotoCoreError as e:
            raise StorageUploadError(str(e)) from e

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise KeyError(key) from e
            raise StorageUploadError(f"get object failed: {e}") from e
        except BotoCoreError as e:
            raise StorageUploadError(str(e)) from e


_storage_singleton: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    """Lazy singleton for app lifetime."""
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton
    s = get_settings()
    if s.use_fake_storage:
        _storage_singleton = InMemoryObjectStorage(bucket=s.s3_bucket)
        return _storage_singleton
    _storage_singleton = S3ObjectStorage(
        bucket=s.s3_bucket,
        endpoint_url=s.s3_endpoint_url,
        access_key_id=s.s3_access_key_id,
        secret_access_key=s.s3_secret_access_key,
        region=s.s3_region,
        use_path_style=s.s3_use_path_style,
    )
    return _storage_singleton


def reset_object_storage() -> None:
    global _storage_singleton
    _storage_singleton = None
