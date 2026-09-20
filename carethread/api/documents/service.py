"""Documents domain service coordinating storage and single-table metadata persistence."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType
from carethread.shared.schemas.api import (
    DocumentCreateRequest,
    DocumentCreateResponse,
    DocumentStatusResponse,
)
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.repository.exceptions import DocumentNotFoundError
from carethread.shared.storage.interfaces import StorageServiceInterface

logger = logging.getLogger(__name__)

# Long enough to read a document without a refresh, short enough that a leaked
# URL expires quickly.
PAGE_URL_TTL_SECONDS = 900


class DocumentsService:
    """Business logic for document registration and presigned upload generation."""

    def __init__(
        self,
        repository: PatientRepositoryInterface,
        storage: StorageServiceInterface
    ):
        self.repo = repository
        self.storage = storage

    def create_document(
        self,
        patient_id: str,
        request: DocumentCreateRequest
    ) -> DocumentCreateResponse:
        """Register an uploading document, persist metadata, and return presigned S3 PUT URL.

        Status initialized to 'uploading' per Section 6 lifecycle.
        S3 Key pattern: raw/<patient_id>/<doc_id>.<ext>
        Presigned URL expiry: 300 seconds per Section 4.2.
        """
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")

        doc_id = f"d_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Generate S3 key and presigned upload URL
        s3_key, upload_url = self.storage.generate_upload_url(
            patient_id=patient_id,
            doc_id=doc_id,
            filename=request.filename,
            content_type=request.content_type,
            expires_in=300
        )

        # Create canonical Document domain record
        document = Document(
            patient_id=patient_id,
            doc_id=doc_id,
            type=DocumentType.UNKNOWN,
            s3_key=s3_key,
            status=DocumentStatus.UPLOADING,
            pages=[],
            created_at=now_iso,
            updated_at=now_iso
        )

        # Persist through DynamoDB repository
        self.repo.create_document(document)

        return DocumentCreateResponse(
            doc_id=doc_id,
            upload_url=upload_url
        )

    def get_document_status(
        self,
        patient_id: str,
        doc_id: str
    ) -> DocumentStatusResponse:
        """Fetch document status for UI progress tracking."""
        document = self.repo.get_document(patient_id, doc_id)
        if not document:
            raise DocumentNotFoundError(f"Document {doc_id} not found for patient {patient_id}")

        pages_list = document.pages if isinstance(document.pages, list) else []

        # The document was fetched patient-scoped, so every page key below is
        # inside this patient's own prefix; a presigned URL cannot be minted
        # for another partition's object.
        page_urls: List[str] = []
        for key in pages_list:
            try:
                page_urls.append(
                    self.storage.generate_download_url(key, expires_in=PAGE_URL_TTL_SECONDS)
                )
            except Exception:
                logger.warning("Could not presign page %s for document %s", key, doc_id)
                page_urls = []
                break

        return DocumentStatusResponse(
            doc_id=document.doc_id,
            status=document.status,
            type=document.type,
            pages=pages_list,
            page_urls=page_urls,
            error=document.error_reason
        )

    def delete_document(self, patient_id: str, doc_id: str) -> bool:
        """Delete document from repository."""
        if not patient_id or not str(patient_id).strip():
            raise ValueError("patient_id must be a non-empty string")
        doc = self.repo.get_document(patient_id, doc_id)
        if not doc:
            raise DocumentNotFoundError(f"Document {doc_id} not found for patient {patient_id}")
        return self.repo.delete_document(patient_id, doc_id)
