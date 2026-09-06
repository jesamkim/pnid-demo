"""OCR agent — Textract wrapper that returns text blocks with bboxes.

The Vision LLM gives us *what* and *roughly where*; Textract gives us
*exactly where the text is*. The Fusion agent later marries them.

This module is intentionally not a Strands `Agent` itself — Textract
is a single deterministic AWS call, so a tool function is the right
shape. The orchestrator can wrap it in a Strands `@tool` if it wants
to expose it through an LLM agent loop, but it isn't required for our
fan-out.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image

from backend.aws_clients import get_session


def _ocr_backend() -> str:
    """`textract` (default) or `bda`. Set via `OCR_BACKEND` env. Read at
    call time so an ECS task definition swap takes effect on the next
    request, no process restart needed."""
    return os.getenv("OCR_BACKEND", "textract").strip().lower()


@dataclass(frozen=True)
class TextBlock:
    text: str
    confidence: float
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) in px


def _client():
    return get_session().client("textract")


def _normalise_bbox(box: dict, img_w: int, img_h: int) -> tuple[float, float, float, float]:
    # Textract returns bbox as { Left, Top, Width, Height } normalised to 0..1
    left = box["Left"] * img_w
    top = box["Top"] * img_h
    right = (box["Left"] + box["Width"]) * img_w
    bottom = (box["Top"] + box["Height"]) * img_h
    return (round(left, 1), round(top, 1), round(right, 1), round(bottom, 1))


def _to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def detect_text_blocks(image: Image.Image | Path) -> tuple[TextBlock, ...]:
    """Run the configured OCR backend on a PIL image or file path.

    Returns a tuple of `TextBlock` instances in canvas pixel coordinates.
    With `OCR_BACKEND=bda` the call is routed to the BDA adapter; the
    default is Textract (the long-standing path).
    """
    if _ocr_backend() == "bda":
        # Lazy import so the import graph stays clean when running unit
        # tests that have no boto3 / S3 / BDA available.
        from backend.agents import bda_ocr
        return bda_ocr.detect_text_blocks(image)

    if isinstance(image, Path):
        image = Image.open(image)
    img = image.convert("RGB")
    payload = _to_png_bytes(img)
    resp = _client().detect_document_text(Document={"Bytes": payload})
    w, h = img.size
    blocks: list[TextBlock] = []
    for b in resp.get("Blocks", []):
        if b.get("BlockType") != "LINE":
            continue
        text = (b.get("Text") or "").strip()
        if not text:
            continue
        geom = b.get("Geometry") or {}
        bbox_norm = geom.get("BoundingBox") or {}
        if not bbox_norm:
            continue
        blocks.append(TextBlock(
            text=text,
            confidence=float(b.get("Confidence") or 0.0),
            bbox=_normalise_bbox(bbox_norm, w, h),
        ))
    return tuple(blocks)


def detect_text_blocks_from_bytes(payload: bytes) -> tuple[TextBlock, ...]:
    """Same as `detect_text_blocks` but takes raw PDF/PNG bytes."""
    if _ocr_backend() == "bda":
        from backend.agents import bda_ocr
        return bda_ocr.detect_text_blocks_from_bytes(payload)
    img = Image.open(io.BytesIO(payload)).convert("RGB")
    return detect_text_blocks(img)


def filter_label_candidates(
    blocks: Sequence[TextBlock],
    *,
    max_chars: int = 24,
) -> tuple[TextBlock, ...]:
    """Drop blocks that are obviously not P&ID tags or line numbers.

    Heuristic: tags look like ``V-101``, ``PSV-101``, ``12"-CRD-101-CS``;
    they have at least one digit and a hyphen, and are short. Title
    blocks ("PROJECT: ROADSHOW DEMO") are filtered out by the
    `max_chars` guard.
    """
    out: list[TextBlock] = []
    for b in blocks:
        t = b.text
        if len(t) > max_chars:
            continue
        if not any(c.isdigit() for c in t):
            continue
        out.append(b)
    return tuple(out)
