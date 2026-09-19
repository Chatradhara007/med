"""Rasterise state: PDF or camera photo -> page PNGs in S3.

Writes ``pages/<patient_id>/<doc_id>/p<N>.png`` at 150 DPI for UI display and
bounding-box overlay, and records the page keys on the document row.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any, Dict, List, Optional

from carethread.pipeline.common import (
    PipelineError,
    UnsupportedDocumentError,
    envelope_from_event,
    fetch_object,
    get_pipeline_repository,
    page_key,
    put_object,
    update_document_status,
)
from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.schemas.document import DocumentStatus

logger = logging.getLogger(__name__)

RASTER_DPI = 150
MAX_PAGES = int(os.environ.get("MAX_RASTER_PAGES", "20"))

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "heic", "tif", "tiff"}


def _render_pdf_pages(pdf_bytes: bytes) -> List[bytes]:
    """Render PDF pages to PNG bytes.

    Uses PyMuPDF when the layer provides it, else pdf2image/poppler. Both are
    optional at import time so that a deployment carrying neither still fails
    with a clear, patient-visible reason instead of an ImportError traceback.
    """
    try:
        import fitz  # PyMuPDF

        pages: List[bytes] = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc[:MAX_PAGES]:
                pixmap = page.get_pixmap(dpi=RASTER_DPI)
                pages.append(pixmap.tobytes("png"))
        return pages
    except ImportError:
        pass

    try:
        from pdf2image import convert_from_bytes
    except ImportError as exc:
        raise UnsupportedDocumentError(
            "No PDF rasteriser available in this runtime (install PyMuPDF or pdf2image)"
        ) from exc

    images = convert_from_bytes(pdf_bytes, dpi=RASTER_DPI)[:MAX_PAGES]
    pages = []
    for image in images:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        pages.append(buffer.getvalue())
    return pages


def _normalise_image(image_bytes: bytes) -> bytes:
    """Re-encode a camera photo as PNG so every page key has one format."""
    try:
        from PIL import Image
    except ImportError:
        # Without Pillow the original bytes are still a readable image for the
        # vision model; only the .png extension is then cosmetic.
        logger.info("Pillow unavailable; storing uploaded image unchanged")
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgb = image.convert("RGB")
            buffer = io.BytesIO()
            rgb.save(buffer, format="PNG")
            return buffer.getvalue()
    except Exception as exc:
        raise UnsupportedDocumentError(f"Uploaded file is not a readable image: {exc}") from exc


def rasterise_document(
    event: Dict[str, Any],
    repository: Optional[PatientRepositoryInterface] = None,
    s3_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Rasterise an uploaded document into page images."""
    envelope = envelope_from_event(event)
    patient_id = envelope["patient_id"]
    doc_id = envelope["doc_id"]
    bucket = envelope["bucket"]
    key = envelope.get("key")
    repo = get_pipeline_repository(repository)

    update_document_status(repo, patient_id, doc_id, DocumentStatus.RASTERISING)

    if not key:
        raise PipelineError(f"No raw S3 key on the envelope for document {doc_id}")

    raw_bytes = fetch_object(bucket, key, s3_client=s3_client)
    if not raw_bytes:
        raise UnsupportedDocumentError(f"Uploaded object s3://{bucket}/{key} is empty")

    extension = (envelope.get("extension") or key.rsplit(".", 1)[-1]).lower()

    if extension == "pdf":
        page_images = _render_pdf_pages(raw_bytes)
    elif extension in IMAGE_EXTENSIONS:
        page_images = [_normalise_image(raw_bytes)]
    else:
        raise UnsupportedDocumentError(f"Unsupported upload format '.{extension}'")

    if not page_images:
        raise UnsupportedDocumentError("Document produced zero readable pages")

    page_keys: List[str] = []
    for index, image_bytes in enumerate(page_images, start=1):
        target = page_key(patient_id, doc_id, index)
        put_object(bucket, target, image_bytes, content_type="image/png", s3_client=s3_client)
        page_keys.append(target)

    update_document_status(
        repo,
        patient_id,
        doc_id,
        DocumentStatus.CLASSIFYING,
        pages=page_keys,
    )

    envelope["pages"] = page_keys
    envelope["page_count"] = len(page_keys)
    logger.info("Rasterised document %s into %d page(s)", doc_id, len(page_keys))
    return envelope


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda entrypoint for the Rasterise state."""
    return rasterise_document(event)
