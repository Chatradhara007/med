"""Tests for PDF and photo rasterisation.

Rasterise is the first state in the pipeline and the one most likely to fail
on a real upload, so the renderer's absence, its fallback order and its
failure message are all pinned here.
"""

import io
import zlib

import pytest

from carethread.pipeline.common import UnsupportedDocumentError, page_key
from carethread.pipeline.rasterise import handler as rasterise
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.schemas.document import Document, DocumentStatus, DocumentType

PATIENT = "pt_raster_001"
DOC = "d_raster01"
BUCKET = "carethread-docs-test"

def _renderer_installed() -> bool:
    for _, render in rasterise._RENDERERS:
        try:
            if render(b"%PDF-1.4\n%%EOF\n") is not None:
                return True
        except Exception:
            # Present but rejected this stub: still installed.
            return True
    return False


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.puts = {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": self.objects[Key]}

    def put_object(self, Bucket, Key, Body, ContentType=None, ServerSideEncryption=None):
        self.puts[Key] = Body
        return {}


@pytest.fixture
def repo():
    repository = InMemoryPatientRepository()
    repository.create_document(
        Document(
            patient_id=PATIENT,
            doc_id=DOC,
            type=DocumentType.UNKNOWN,
            s3_key=f"raw/{PATIENT}/{DOC}.pdf",
            status=DocumentStatus.UPLOADED,
            pages=[],
            created_at="2026-09-19T10:00:00+00:00",
            updated_at="2026-09-19T10:00:00+00:00",
        )
    )
    return repository


def _make_pdf(page_count=2) -> bytes:
    """A minimal but genuinely valid multi-page PDF, built by hand.

    Cheaper and clearer than committing a binary fixture, and it exercises the
    real rendering path rather than a stub.
    """
    objects = []
    kids = " ".join(f"{3 + i} 0 R" for i in range(page_count))
    objects.append(f"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>"
    )
    for i in range(page_count):
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {3 + page_count + i} 0 R >>"
        )
    for i in range(page_count):
        stream = f"BT /F1 24 Tf 72 700 Td (Page {i + 1}) Tj ET".encode()
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _png(width=8, height=8):
    """A tiny valid PNG, built without Pillow."""
    import struct

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# ==================================================
# 1. Renderer selection and absence
# ==================================================

def test_renderers_are_ordered_by_licence_then_self_containment():
    names = [name for name, _ in rasterise._RENDERERS]
    assert names == ["pypdfium2", "PyMuPDF", "pdf2image"]


def test_absent_renderer_gives_an_actionable_message(monkeypatch):
    """A deployment with no engine must say so, not raise ImportError."""
    monkeypatch.setattr(rasterise, "_RENDERERS", (("none", lambda _: None),))

    with pytest.raises(UnsupportedDocumentError) as excinfo:
        rasterise._render_pdf_pages(b"%PDF-1.4")
    assert "PdfRenderLayer" in str(excinfo.value)


def test_a_failing_renderer_falls_through_to_the_next(monkeypatch):
    def broken(_):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(
        rasterise,
        "_RENDERERS",
        (("broken", broken), ("working", lambda _: [b"page-bytes"])),
    )
    assert rasterise._render_pdf_pages(b"%PDF-1.4") == [b"page-bytes"]


def test_a_corrupt_pdf_reports_why_not_how(monkeypatch):
    def broken(_):
        raise RuntimeError("not a PDF")

    monkeypatch.setattr(rasterise, "_RENDERERS", (("broken", broken),))
    with pytest.raises(UnsupportedDocumentError) as excinfo:
        rasterise._render_pdf_pages(b"garbage")
    assert "could not be opened" in str(excinfo.value)


def test_a_pdf_with_zero_pages_is_unsupported(monkeypatch):
    monkeypatch.setattr(rasterise, "_RENDERERS", (("empty", lambda _: []),))
    with pytest.raises(UnsupportedDocumentError):
        rasterise._render_pdf_pages(b"%PDF-1.4")


# ==================================================
# 2. Real rendering, when an engine is installed
# ==================================================

@pytest.mark.skipif(not _renderer_installed(), reason="no PDF renderer installed")
def test_renders_a_real_pdf_to_png_pages():
    pages = rasterise._render_pdf_pages(_make_pdf(page_count=2))

    assert len(pages) == 2
    for page in pages:
        assert page.startswith(b"\x89PNG\r\n\x1a\n"), "pages must be PNG"
        # 150 DPI on US Letter is ~1275x1650; a stub would be far smaller.
        assert len(page) > 500


@pytest.mark.skipif(not _renderer_installed(), reason="no PDF renderer installed")
def test_page_cap_is_respected(monkeypatch):
    monkeypatch.setattr(rasterise, "MAX_PAGES", 2)
    assert len(rasterise._render_pdf_pages(_make_pdf(page_count=6))) == 2


# ==================================================
# 3. Photos
# ==================================================

def test_camera_photo_is_stored_as_a_single_page(repo):
    s3 = FakeS3({f"raw/{PATIENT}/{DOC}.png": _png()})
    result = rasterise.rasterise_document(
        {"patient_id": PATIENT, "doc_id": DOC, "bucket": BUCKET,
         "key": f"raw/{PATIENT}/{DOC}.png", "extension": "png"},
        repository=repo,
        s3_client=s3,
    )

    assert result["pages"] == [page_key(PATIENT, DOC, 1)]
    assert page_key(PATIENT, DOC, 1) in s3.puts
    assert repo.get_document(PATIENT, DOC).status == DocumentStatus.CLASSIFYING


def test_unreadable_photo_is_rejected(repo):
    s3 = FakeS3({f"raw/{PATIENT}/{DOC}.png": b"this is not an image"})
    with pytest.raises(UnsupportedDocumentError):
        rasterise.rasterise_document(
            {"patient_id": PATIENT, "doc_id": DOC, "bucket": BUCKET,
             "key": f"raw/{PATIENT}/{DOC}.png", "extension": "png"},
            repository=repo,
            s3_client=s3,
        )


def test_unsupported_extension_is_rejected(repo):
    s3 = FakeS3({f"raw/{PATIENT}/{DOC}.docx": b"PK\x03\x04"})
    with pytest.raises(UnsupportedDocumentError) as excinfo:
        rasterise.rasterise_document(
            {"patient_id": PATIENT, "doc_id": DOC, "bucket": BUCKET,
             "key": f"raw/{PATIENT}/{DOC}.docx", "extension": "docx"},
            repository=repo,
            s3_client=s3,
        )
    assert "docx" in str(excinfo.value)


def test_empty_upload_is_rejected(repo):
    s3 = FakeS3({f"raw/{PATIENT}/{DOC}.pdf": b""})
    with pytest.raises(UnsupportedDocumentError):
        rasterise.rasterise_document(
            {"patient_id": PATIENT, "doc_id": DOC, "bucket": BUCKET,
             "key": f"raw/{PATIENT}/{DOC}.pdf", "extension": "pdf"},
            repository=repo,
            s3_client=s3,
        )


# ==================================================
# 4. The layer is actually wired in the template
# ==================================================

def _template():
    import pathlib
    import re

    import yaml

    src = pathlib.Path(__file__).resolve().parents[1] / "infra" / "template.yaml"
    return yaml.safe_load(re.sub(r"!\w+\s", "", src.read_text()))


def test_template_defines_the_pdf_layer():
    layer = _template()["Resources"]["PdfRenderLayer"]
    assert layer["Properties"]["CompatibleRuntimes"] == ["python3.11"]
    assert layer["Metadata"]["BuildMethod"] == "python3.11"


def test_layer_is_attached_to_the_rasteriser_and_nothing_else():
    resources = _template()["Resources"]
    assert resources["RasteriseFn"]["Properties"]["Layers"] == ["PdfRenderLayer"]

    for name, resource in resources.items():
        if name == "RasteriseFn" or resource.get("Type") != "AWS::Serverless::Function":
            continue
        assert "Layers" not in resource["Properties"], (
            f"{name} should not carry the PDF engine"
        )


def test_layer_requirements_pin_a_permissively_licensed_engine():
    import pathlib

    reqs = (
        pathlib.Path(__file__).resolve().parents[1] / "infra" / "layers" / "pdf" / "requirements.txt"
    ).read_text().lower()
    assert "pypdfium2" in reqs
    assert "pillow" in reqs
