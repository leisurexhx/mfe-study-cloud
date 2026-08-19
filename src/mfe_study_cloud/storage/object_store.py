"""Object storage adapters; clients never supply keys to these methods directly."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from mfe_study_cloud.config import Settings


class ObjectStore(Protocol):
    def ensure_ready(self) -> None: ...

    def put(self, key: str, data: bytes, *, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


def document_object_key(tenant_id: uuid.UUID, document_id: uuid.UUID) -> str:
    return f"tenants/{tenant_id}/documents/{document_id}/source.pdf"


def rendered_page_object_key(
    tenant_id: uuid.UUID, document_id: uuid.UUID, page_number: int, width: int
) -> str:
    if page_number < 1:
        raise ValueError("Page number must be positive.")
    bounded_width = max(640, min(width, 2000))
    return (
        f"tenants/{tenant_id}/documents/{document_id}/pages/"
        f"page-{page_number:05d}-w{bounded_width}.png"
    )


@dataclass(slots=True)
class InMemoryObjectStore:
    """Isolated test store; never used as an implicit production fallback."""

    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    def ensure_ready(self) -> None:
        return None

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self.objects[key] = (bytes(data), content_type)

    def get(self, key: str) -> bytes:
        try:
            return self.objects[key][0]
        except KeyError as exc:
            raise FileNotFoundError("Object does not exist.") from exc

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class S3ObjectStore:
    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._bucket = settings.object_bucket
        if client is None:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.object_endpoint,
                region_name=settings.object_region,
                aws_access_key_id=settings.object_access_key.get_secret_value(),
                aws_secret_access_key=settings.object_secret_key.get_secret_value(),
                use_ssl=settings.object_secure,
            )
        self._client = client

    def ensure_ready(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    def put(self, key: str, data: bytes, *, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise FileNotFoundError("Object does not exist.") from exc
        body = response["Body"]
        return bytes(body.read())

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
