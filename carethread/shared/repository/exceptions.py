"""Repository exception definitions for CareThread.

Isolates database and validation errors from upper application layers.
"""


class RepositoryError(Exception):
    """Base exception for all repository-layer operations."""
    pass


class PatientNotFoundError(RepositoryError):
    """Raised when a requested patient does not exist."""
    pass


class DocumentNotFoundError(RepositoryError):
    """Raised when a requested document does not exist."""
    pass


class EntityNotFoundError(RepositoryError):
    """Raised when a specific clinical entity is not found."""
    pass


class ValidationError(RepositoryError):
    """Raised when data fails domain or schema validation before storage."""
    pass


class MissingProvenanceError(ValidationError):
    """Raised when an extracted clinical entity lacks required provenance."""
    pass


class InvalidPatientIdError(ValidationError):
    """Raised when an invalid patient identifier is provided."""
    pass


class DatabaseError(RepositoryError):
    """Raised when DynamoDB or underlying persistence operation fails."""
    pass
