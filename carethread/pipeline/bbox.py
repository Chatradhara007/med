"""Bounding box derivation by verbatim string matching (Section 10.3).

Full-fidelity bbox extraction from a vision model is expensive and slow. The
build documentation prescribes the cheaper route: the model returns
``source.verbatim``, and we locate that string in the document's text layer to
derive the box. When the string cannot be located we fall back to a page-level
highlight rather than dropping the citation -- a coarse box is still a real
source, an absent box breaks the one invariant.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Provenance boxes are [ymin, xmin, ymax, xmax] on a 0-1000 grid.
FULL_PAGE_BBOX: List[float] = [0.0, 0.0, 1000.0, 1000.0]

_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapse whitespace and case so OCR spacing noise does not defeat a match."""
    return _WS.sub(" ", (text or "").strip()).lower()


class TextLayer:
    """A document's extracted text, optionally with per-word geometry.

    ``page_texts`` is required and drives page attribution. ``word_boxes`` is
    optional: when a geometry-bearing OCR source (for example Amazon Textract)
    is available, supplying it upgrades the page-level highlight into a real
    region box at no extra model cost.
    """

    def __init__(
        self,
        page_texts: Sequence[str],
        word_boxes: Optional[Sequence[Sequence[Dict[str, Any]]]] = None,
    ) -> None:
        self.page_texts: List[str] = [t or "" for t in page_texts]
        self.word_boxes: List[List[Dict[str, Any]]] = (
            [list(page) for page in word_boxes] if word_boxes else []
        )

    @property
    def page_count(self) -> int:
        return len(self.page_texts)

    def find_page(self, verbatim: str) -> Optional[int]:
        """Return the 1-indexed page containing the verbatim string, if any."""
        needle = normalise(verbatim)
        if not needle:
            return None
        for index, text in enumerate(self.page_texts):
            if needle in normalise(text):
                return index + 1
        # Fall back to the longest distinctive fragment; OCR frequently breaks
        # a line across two text runs.
        fragments = [f for f in needle.split(" ") if len(f) > 3]
        if not fragments:
            return None
        longest = max(fragments, key=len)
        for index, text in enumerate(self.page_texts):
            if longest in normalise(text):
                return index + 1
        return None

    def find_bbox(self, verbatim: str, page: int) -> Optional[List[float]]:
        """Derive a box by unioning the geometry of the matched words."""
        if not self.word_boxes or page < 1 or page > len(self.word_boxes):
            return None
        words = self.word_boxes[page - 1]
        if not words:
            return None

        targets = [w for w in normalise(verbatim).split(" ") if w]
        if not targets:
            return None
        matched = [w for w in words if normalise(str(w.get("text", ""))) in targets]
        if not matched:
            return None

        try:
            ymins = [float(w["ymin"]) for w in matched]
            xmins = [float(w["xmin"]) for w in matched]
            ymaxs = [float(w["ymax"]) for w in matched]
            xmaxs = [float(w["xmax"]) for w in matched]
        except (KeyError, TypeError, ValueError):
            logger.warning("Word geometry on page %s is malformed; using page highlight", page)
            return None

        return _clamp([min(ymins), min(xmins), max(ymaxs), max(xmaxs)])


def _clamp(bbox: Sequence[float]) -> List[float]:
    """Clamp to the 0-1000 grid and repair inverted edges."""
    ymin, xmin, ymax, xmax = (max(0.0, min(1000.0, float(v))) for v in bbox)
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    if xmin > xmax:
        xmin, xmax = xmax, xmin
    return [ymin, xmin, ymax, xmax]


def derive_source_location(
    verbatim: str,
    text_layer: Optional[TextLayer] = None,
    default_page: int = 1,
) -> Tuple[int, List[float], bool]:
    """Locate a verbatim string in the document.

    Returns ``(page, bbox, located)``. ``located`` is False when the string was
    not found and the caller is receiving a page-level highlight, which the UI
    renders as a whole-page citation instead of a tight overlay.
    """
    if text_layer is None or text_layer.page_count == 0:
        return default_page, list(FULL_PAGE_BBOX), False

    page = text_layer.find_page(verbatim)
    if page is None:
        return default_page, list(FULL_PAGE_BBOX), False

    bbox = text_layer.find_bbox(verbatim, page)
    if bbox is None:
        return page, list(FULL_PAGE_BBOX), False
    return page, bbox, True


def extract_pdf_text_layer(pdf_bytes: bytes) -> Optional[TextLayer]:
    """Pull the text layer out of a PDF, when it has one.

    Scanned PDFs carry no text layer; that is expected and simply means
    citations fall back to page-level highlights.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.info("pypdf unavailable; skipping text-layer extraction")
        return None

    import io

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        logger.warning("Could not read PDF text layer: %s", exc)
        return None

    if not any(p.strip() for p in pages):
        return None
    return TextLayer(page_texts=pages)
