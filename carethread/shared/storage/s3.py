"""Production S3 storage service implementing presigned PUT URL generation."""

import os
from typing import Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError
from .interfaces import StorageServiceInterface
from .in_memory import extract_extension


class S3StorageService(StorageServiceInterface):
    """Production AWS S3 storage implementation."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        s3_client: Optional[Any] = None,
        region_name: Optional[str] = None
    ):
        self.bucket_name = bucket_name or os.environ.get("DOC_BUCKET", "carethread-docs")
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        if s3_client:
            self._s3 = s3_client
        else:
            self._s3 = boto3.client("s3", region_name=self.region_name)

    def get_s3_key(self, patient_id: str, doc_id: str, filename: str, content_type: str = "") -> str:
        """Deterministic S3 object key convention per Section 4.2.

        Pattern: raw/<patient_id>/<doc_id>.<ext>
        """
        ext = extract_extension(filename, content_type)
        return f"raw/{patient_id}/{doc_id}.{ext}"

    def generate_download_url(self, s3_key: str, expires_in: int = 900) -> str:
        """Presigned GET URL so the UI can render a page image it cannot fetch directly."""
        if not s3_key or not s3_key.strip():
            raise ValueError("s3_key must be a non-empty string")
        try:
            return self._s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to generate S3 presigned download URL: {e}") from e

    def generate_upload_url(
        self,
        patient_id: str,
        doc_id: str,
        filename: str,
        content_type: str,
        expires_in: int = 300
    ) -> Tuple[str, str]:
        """Generate a presigned S3 PUT URL valid for 300 seconds."""
        s3_key = self.get_s3_key(patient_id, doc_id, filename, content_type)
        try:
            url = self._s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
            return s3_key, url
        except ClientError as e:
            raise RuntimeError(f"Failed to generate S3 presigned upload URL: {e}") from e
