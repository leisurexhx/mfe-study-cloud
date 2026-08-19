from __future__ import annotations

import uuid
from io import BytesIO
from typing import Any

import pytest
from botocore.exceptions import ClientError

from mfe_study_cloud.config import Settings
from mfe_study_cloud.storage import (
    S3ObjectStore,
    document_object_key,
    rendered_page_object_key,
)


class FakeS3Client:
    def __init__(
        self,
        *,
        head_error: str | None = None,
        create_error: str | None = None,
    ) -> None:
        self.head_error = head_error
        self.create_error = create_error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def head_bucket(self, **kwargs: Any) -> None:
        self.calls.append(("head", kwargs))
        if self.head_error:
            raise ClientError(
                {"Error": {"Code": self.head_error, "Message": "test"}},
                "HeadBucket",
            )

    def create_bucket(self, **kwargs: Any) -> None:
        self.calls.append(("create", kwargs))
        if self.create_error:
            raise ClientError(
                {"Error": {"Code": self.create_error, "Message": "test"}},
                "CreateBucket",
            )

    def put_object(self, **kwargs: Any) -> None:
        self.calls.append(("put", kwargs))

    def get_object(self, **kwargs: Any) -> dict[str, BytesIO]:
        self.calls.append(("get", kwargs))
        return {"Body": BytesIO(b"stored")}

    def delete_object(self, **kwargs: Any) -> None:
        self.calls.append(("delete", kwargs))


def _settings() -> Settings:
    return Settings(
        MFE_ENV="test",
        MFE_OBJECT_BUCKET="unit-test-bucket",
        MFE_OBJECT_SSE="AES256",
    )


def test_s3_store_creates_only_a_missing_bucket_and_encrypts_puts() -> None:
    client = FakeS3Client(head_error="NoSuchBucket")
    store = S3ObjectStore(_settings(), client=client)

    store.ensure_ready()
    store.put("server/generated", b"pdf", content_type="application/pdf")
    assert store.get("server/generated") == b"stored"
    store.delete("server/generated")

    assert [name for name, _ in client.calls] == ["head", "create", "put", "get", "delete"]
    put = client.calls[2][1]
    assert put["ServerSideEncryption"] == "AES256"
    assert put["Bucket"] == "unit-test-bucket"


def test_s3_store_does_not_mask_permission_errors_as_missing_buckets() -> None:
    client = FakeS3Client(head_error="AccessDenied")
    store = S3ObjectStore(_settings(), client=client)

    with pytest.raises(ClientError):
        store.ensure_ready()
    assert [name for name, _ in client.calls] == ["head"]


def test_s3_store_tolerates_another_worker_winning_bucket_creation_race() -> None:
    client = FakeS3Client(
        head_error="NoSuchBucket",
        create_error="BucketAlreadyOwnedByYou",
    )

    S3ObjectStore(_settings(), client=client).ensure_ready()

    assert [name for name, _ in client.calls] == ["head", "create"]


def test_object_keys_are_server_scoped_and_render_width_is_bounded() -> None:
    tenant_id = uuid.uuid4()
    document_id = uuid.uuid4()

    assert document_object_key(tenant_id, document_id) == (
        f"tenants/{tenant_id}/documents/{document_id}/source.pdf"
    )
    assert rendered_page_object_key(tenant_id, document_id, 3, 10).endswith(
        "/page-00003-w640.png"
    )
    assert rendered_page_object_key(tenant_id, document_id, 3, 99_999).endswith(
        "/page-00003-w2000.png"
    )
    with pytest.raises(ValueError):
        rendered_page_object_key(tenant_id, document_id, 0, 1000)
