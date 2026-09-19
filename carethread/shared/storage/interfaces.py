"""Storage abstraction interface for CareThread document files.

Follows Section 4.2 S3 Layout:
s3://carethread-docs-<acct>/
raw/<patient_id>/<doc_id>.<ext>
pages/<patient_id>/<doc_id>/p<N>.png
Presigned URLs expire in 300 seconds.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple


class StorageServiceInterface(ABC):
    """Abstract interface for object storage operations."""

    @abstractmethod
    def generate_upload_url(
        self,
        patient_id: str,
        doc_id: str,
        filename: str,
        content_type: str,
        expires_in: int = 300
    ) -> Tuple[str, str]:
        """Generate a deterministic S3 key and presigned upload URL.

        Returns:
            Tuple[str, str]: (s3_key, presigned_upload_url)
        """
        pass

    @abstractmethod
    def get_s3_key(self, patient_id: str, doc_id: str, filename: str) -> str:
        """Deterministic S3 object key convention per Section 4.2.

        Pattern: raw/<patient_id>/<doc_id>.<ext>
        """
        pass
