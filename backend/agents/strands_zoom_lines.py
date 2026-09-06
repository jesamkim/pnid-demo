"""Zoom-in pass: crop the union of OCR line-label bboxes and run a
focused Vision sub-call on it.

When the source drawing is wide (e.g. 7800×3000) and labels are
small relative to the page, the main Vision pass can miss line
numbers that *are* visible — they're just tiny pixels among many
other tiny pixels. Cropping a tighter bounding box that contains
only the OCR-confirmed line-label regions and running another
Vision pass on it gives the model an effective magnification of
3-5×, recovering missed labels without GT lookup.

Generic — never references a drawing-id or specific tag.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from PIL import Image

from backend.agents.line_refinement import (
    _LINE_NO_RE, _normalise, find_line_candidates,
)
from backend.agents.strands_extractor import extract_from_image
from backend.agents.strands_ocr import TextBlock
from backend.schemas import ExtractionResult, Line


def _bbox_union(blocks: Sequence[TextBlock]) -> tuple[int, int, int, int] | None:
    if not blocks:
        return None
    xs1 = min(b.bbox[0] for b in blocks)
    ys1 = min(b.bbox[1] for b in blocks)
    xs2 = max(b.bbox[2] for b in blocks)
    ys2 = max(b.bbox[3] for b in blocks)
    return (int(xs1), int(ys1), int(xs2), int(ys2))


def zoom_into_line_region(
    image: Image.Image,
    blocks: Sequence[TextBlock],
    *,
    min_blocks: int = 4,
    pad_px: int = 80,
) -> Image.Image | None:
    """Return a tightly-cropped sub-image around the union of OCR
    blocks whose text matches the line-number grammar — or None when
    there are too few candidates to bother with."""
    line_blocks = [
        b for b in blocks if _LINE_NO_RE.search(b.text or "")
    ]
    if len(line_blocks) < min_blocks:
        return None
    bbox = _bbox_union(line_blocks)
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    w, h = image.size
    x1 = max(0, x1 - pad_px)
    y1 = max(0, y1 - pad_px)
    x2 = min(w, x2 + pad_px)
    y2 = min(h, y2 + pad_px)
    if x2 - x1 < 200 or y2 - y1 < 200:
        return None
    return image.crop((x1, y1, x2, y2))


def merge_zoom_lines(
    base: ExtractionResult,
    zoom_lines: tuple[Line, ...],
) -> tuple[ExtractionResult, dict]:
    """Add any zoom-pass line whose canonical form is missing from the
    base extraction. Never overwrite an existing line — the zoom pass
    is a recall booster only."""
    seen = {_normalise(l.line_no) for l in base.lines}
    added: list[Line] = []
    for l in zoom_lines:
        n = _normalise(l.line_no)
        if n in seen or not n:
            continue
        seen.add(n)
        added.append(l)
    if not added:
        return base, {"zoom_added": 0}
    return replace(base, lines=tuple(list(base.lines) + added)), {
        "zoom_added": len(added),
    }


def zoom_pass(
    image: Image.Image,
    drawing_id: str,
    extraction: ExtractionResult,
    blocks: Sequence[TextBlock],
) -> tuple[ExtractionResult, dict]:
    """Top-level entry. Crops to OCR-line region, runs Vision focused
    on lines, merges new lines into `extraction`."""
    crop = zoom_into_line_region(image, blocks)
    if crop is None:
        return extraction, {"zoom_used": False, "reason": "insufficient OCR"}
    candidates = tuple(find_line_candidates(blocks))
    try:
        zoomed_extraction, _meta = extract_from_image(
            crop,
            drawing_id=drawing_id,
            context_hint=(
                "Zoomed crop centred on OCR line-label region. ONLY return "
                "`lines[]`; equipment/instruments/connections may be empty."
            ),
            line_candidates=candidates,
        )
    except Exception as exc:  # noqa: BLE001
        return extraction, {"zoom_used": False, "reason": f"vision failed: {exc!r}"}
    merged, stats = merge_zoom_lines(extraction, zoomed_extraction.lines)
    return merged, {
        "zoom_used": True,
        "zoom_lines_returned": len(zoomed_extraction.lines),
        **stats,
    }
