"""Bounded S3-compatible object storage behind a small application-facing port."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]{0,199}$")


class ObjectStoreError(RuntimeError):
    """Safe object-store failure that excludes credentials and response bodies."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Verified metadata for one immutable artifact object."""

    key: str
    content_hash: str
    byte_size: int
    media_type: str


class ObjectStore(Protocol):
    """Large-artifact storage contract."""

    async def put(
        self,
        key: str,
        body: bytes,
        *,
        media_type: str,
        expected_hash: str | None = None,
    ) -> StoredObject:
        """Write an object after validating its key and digest."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def get(self, key: str, *, max_bytes: int) -> bytes:
        """Read an object without allowing an unbounded allocation."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def check(self) -> None:
        """Verify that the configured store is reachable and authorized."""

        raise TypeError("protocol declaration has no runtime implementation")


def validate_object_key(key: str) -> str:
    """Reject absolute paths, traversal, control characters, and ambiguous separators."""

    if len(key) > 1000 or key.startswith("/") or "\\" in key:
        raise ValueError("invalid object key")
    segments = key.split("/")
    if not segments or any(
        segment in {"", ".", ".."} or _KEY_SEGMENT.fullmatch(segment) is None
        for segment in segments
    ):
        raise ValueError("invalid object key")
    return key


class S3ObjectStore:
    """S3 adapter with checksum verification, bounded reads, and explicit timeouts."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        region: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                connect_timeout=5,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "standard"},
                signature_version="s3v4",
            ),
        )

    async def ensure_bucket(self) -> None:
        """Create the configured bucket when it is absent in local environments."""

        await asyncio.to_thread(self._ensure_bucket)

    async def check(self) -> None:
        """Check bucket reachability without mutating remote state."""

        await asyncio.to_thread(self._check)

    def _check(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except (BotoCoreError, ClientError) as error:
            raise ObjectStoreError("object-store readiness check failed") from error

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as error:
            status = int(error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if status not in {403, 404}:
                raise ObjectStoreError("object-store bucket check failed") from error
            if status == 403:
                raise ObjectStoreError("object-store bucket is not accessible") from error
            try:
                self._client.create_bucket(Bucket=self._bucket)
            except (BotoCoreError, ClientError) as create_error:
                raise ObjectStoreError("object-store bucket creation failed") from create_error
        except BotoCoreError as error:
            raise ObjectStoreError("object-store bucket check failed") from error

    async def put(
        self,
        key: str,
        body: bytes,
        *,
        media_type: str,
        expected_hash: str | None = None,
    ) -> StoredObject:
        """Upload bytes with an immutable SHA-256 metadata assertion."""

        validated = validate_object_key(key)
        digest = hashlib.sha256(body).hexdigest()
        if expected_hash is not None and not hmac.compare_digest(digest, expected_hash):
            raise ValueError("object content hash does not match expected hash")
        await asyncio.to_thread(self._put, validated, body, media_type, digest)
        return StoredObject(validated, digest, len(body), media_type)

    def _put(self, key: str, body: bytes, media_type: str, digest: str) -> None:
        try:
            self._client.upload_fileobj(
                BytesIO(body),
                self._bucket,
                key,
                ExtraArgs={
                    "ContentType": media_type,
                    "Metadata": {"sha256": digest},
                },
            )
        except (BotoCoreError, ClientError) as error:
            raise ObjectStoreError("object upload failed") from error

    async def get(self, key: str, *, max_bytes: int) -> bytes:
        """Download one object and verify length and optional stored digest."""

        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        return await asyncio.to_thread(self._get, validate_object_key(key), max_bytes)

    def _get(self, key: str, max_bytes: int) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body: BinaryIO = response["Body"]
            value = body.read(max_bytes + 1)
            body.close()
        except (BotoCoreError, ClientError, OSError) as error:
            raise ObjectStoreError("object download failed") from error
        if len(value) > max_bytes:
            raise ObjectStoreError("object exceeds configured read limit")
        expected = response.get("Metadata", {}).get("sha256")
        digest = hashlib.sha256(value).hexdigest()
        if expected is not None and not hmac.compare_digest(digest, expected):
            raise ObjectStoreError("object checksum verification failed")
        return value
