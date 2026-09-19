"""Storage package for CareThread."""

import os
from typing import Optional
from .interfaces import StorageServiceInterface
from .s3 import S3StorageService
from .in_memory import InMemoryStorageService

__all__ = [
    "StorageServiceInterface",
    "S3StorageService",
    "InMemoryStorageService",
    "get_storage_service",
]


def get_storage_service(
    use_memory: Optional[bool] = None,
    bucket_name: Optional[str] = None
) -> StorageServiceInterface:
    """Factory to instantiate storage implementation."""
    if use_memory is None:
        use_memory = os.environ.get("USE_IN_MEMORY_STORAGE", "false").lower() in ("true", "1", "yes")

    if use_memory:
        return InMemoryStorageService(bucket_name=bucket_name or "carethread-docs-mock")
    return S3StorageService(bucket_name=bucket_name)
