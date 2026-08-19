"""S3-compatible object storage boundary."""

from mfe_study_cloud.storage.object_store import (
    InMemoryObjectStore,
    ObjectStore,
    S3ObjectStore,
    document_object_key,
    rendered_page_object_key,
)

__all__ = [
    "InMemoryObjectStore",
    "ObjectStore",
    "S3ObjectStore",
    "document_object_key",
    "rendered_page_object_key",
]
