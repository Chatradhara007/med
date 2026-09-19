"""CareThread repository package."""

import os
from typing import Optional
from .interfaces import PatientRepositoryInterface
from .dynamodb import DynamoDBPatientRepository
from .in_memory import InMemoryPatientRepository
from .exceptions import (
    RepositoryError,
    PatientNotFoundError,
    DocumentNotFoundError,
    EntityNotFoundError,
    ValidationError,
    MissingProvenanceError,
    InvalidPatientIdError,
    DatabaseError,
)

__all__ = [
    "PatientRepositoryInterface",
    "DynamoDBPatientRepository",
    "InMemoryPatientRepository",
    "RepositoryError",
    "PatientNotFoundError",
    "DocumentNotFoundError",
    "EntityNotFoundError",
    "ValidationError",
    "MissingProvenanceError",
    "InvalidPatientIdError",
    "DatabaseError",
    "get_repository",
]


def get_repository(
    use_memory: Optional[bool] = None,
    table_name: Optional[str] = None
) -> PatientRepositoryInterface:
    """Factory to instantiate the appropriate repository implementation."""
    if use_memory is None:
        use_memory = os.environ.get("USE_IN_MEMORY_REPO", "false").lower() in ("true", "1", "yes")

    if use_memory:
        return InMemoryPatientRepository()
    return DynamoDBPatientRepository(table_name=table_name)
