"""In-memory mock storage service for credential-free local development and testing."""

import os
from typing import Dict, Tuple
from .interfaces import StorageServiceInterface


def extract_extension(filename: str, content_type: str) -> str:
    """Extract file extension from filename or fall back to MIME content_type."""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower().strip()
        if ext:
            return ext

    mime_map = {
        "application/pdf": "pdf",
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/webp": "webp",
    }
    return mime_map.get(content_type.lower().strip(), "pdf")


class InMemoryStorageService(StorageServiceInterface):
    """In-memory implementation that produces valid deterministic keys and mock presigned URLs."""

    def __init__(self, bucket_name: str = "carethread-docs-mock"):
        self.bucket_name = bucket_name
        self.generated_urls: Dict[str, dict] = {}

    def get_s3_key(self, patient_id: str, doc_id: str, filename: str, content_type: str = "") -> str:
        ext = extract_extension(filename, content_type)
        return f"raw/{patient_id}/{doc_id}.{ext}"

    def generate_upload_url(
        self,
        patient_id: str,
        doc_id: str,
        filename: str,
        content_type: str,
        expires_in: int = 300
    ) -> Tuple[str, str]:
        s3_key = self.get_s3_key(patient_id, doc_id, filename, content_type)
        mock_url = (
            f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            f"?X-Amz-Expires={expires_in}&mock=true"
        )
        self.generated_urls[s3_key] = {
            "patient_id": patient_id,
            "doc_id": doc_id,
            "filename": filename,
            "content_type": content_type,
            "expires_in": expires_in,
            "upload_url": mock_url,
        }
        return s3_key, mock_url
