"""Fusion agent — combines Vision LLM extraction with Textract OCR bboxes.

Strategy:
  1. For each Vision-detected tag T (equipment + instrument), find the
     OCR text block whose normalised string best matches T (Levenshtein
     ≤ 1 after lowercasing and trimming).
  2. If multiple OCR blocks match, pick the one geometrically closest
     to Vision's coarse bbox (when present) or to the canvas centroid.
  3. Upgrade the Vision bbox to enclose both Vision's coarse box AND
     the OCR label box. If Vision had no bbox, use the OCR label
     directly with a small inflation so it reads as a "bubble" or a
     symbol body.
  4. For each line, collect OCR blocks whose text starts with the
     line_no; emit a polyline through their bbox centres in
     left-to-right reading order.
  5. Emit one event per "fusion_match_*" stage so the timeline shows
     the multi-agent collaboration.

This is intentionally rule-based, not LLM-driven. The Sonnet 4.6
"agent" framing is preserved so the orchestrator and timeline see a
named third agent — but the underlying logic is deterministic which
makes it cheap, fast, and unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from typing import Iterable, Optional, Sequence

from backend.agents.strands_ocr import TextBlock
from backend.schemas import (
    Equipment,
    ExtractionResult,
    Instrument,
    Line,
)


# ---------- helpers --------------------------------------------------------

def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            curr[j] = min(
                prev[j] + 1,        # delete
                curr[j - 1] + 1,    # insert
                prev[j - 1] + (0 if ca == cb else 1),  # substitute
            )
        prev = curr
    return prev[-1]


def _bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _enclose(a, b):
    """Smallest bbox enclosing both a and b. Either may be None."""
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _inflate(bbox, dx: float, dy: float):
    return (bbox[0] - dx, bbox[1] - dy, bbox[2] + dx, bbox[3] + dy)


# ---------- match selection ------------------------------------------------

def _best_match(
    tag: str, blocks: Sequence[TextBlock],
    *, near: Optional[tuple[float, float]] = None,
    max_distance: int = 1,
) -> Optional[TextBlock]:
    n_tag = _normalize(tag)
    candidates: list[tuple[float, TextBlock]] = []
    for b in blocks:
        d = _levenshtein(n_tag, _normalize(b.text))
        if d <= max_distance:
            score = float(d)
            if near is not None:
                cx, cy = _bbox_center(b.bbox)
                score += 1e-4 * ((cx - near[0]) ** 2 + (cy - near[1]) ** 2) ** 0.5
            candidates.append((score, b))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ---------- result --------------------------------------------------------

@dataclass(frozen=True)
class FusionResult:
    extraction: ExtractionResult
    events: tuple[dict, ...]
    matched_equipment: int
    matched_instruments: int
    matched_lines: int


def fuse(
    vision: ExtractionResult,
    ocr_blocks: Sequence[TextBlock],
    *,
    canvas: Optional[tuple[int, int]] = None,
) -> FusionResult:
    """Apply OCR bboxes to upgrade Vision's extraction in place.

    Returns a new `ExtractionResult` plus a tuple of events suitable
    for streaming through the orchestrator's progress callback.
    """
    events: list[dict] = []
    cx_canvas = (canvas[0] / 2) if canvas else None
    cy_canvas = (canvas[1] / 2) if canvas else None

    # Equipment
    new_eq: list[Equipment] = []
    matched_eq = 0
    for eq in vision.equipment:
        near = _bbox_center(eq.bbox) if eq.bbox else (
            (cx_canvas, cy_canvas) if cx_canvas else None
        )
        match = _best_match(eq.tag, ocr_blocks, near=near)
        if match:
            new_bbox = _enclose(eq.bbox, match.bbox)
            new_eq.append(replace(eq, bbox=new_bbox))
            matched_eq += 1
            events.append({
                "stage": "fusion_match_equipment",
                "detail": f"{eq.tag} → OCR bbox {tuple(round(v, 1) for v in match.bbox)}",
                "elapsed_s": 0.0,
                "extra": {"tag": eq.tag, "ocr_text": match.text, "confidence": round(match.confidence, 1)},
            })
        else:
            new_eq.append(eq)
            events.append({
                "stage": "fusion_match_equipment",
                "detail": f"{eq.tag} → no OCR refinement (kept Vision coarse bbox)",
                "elapsed_s": 0.0,
                "extra": {"tag": eq.tag},
            })

    # Instruments — bubble bbox = OCR label inflated, since the bubble
    # is small enough that the text fills it. DIN drawings split the
    # instrument label vertically (function letters on top row, loop_id
    # on bottom row), so the full tag "FRC-F0026" never appears as a
    # single OCR block. We try the full tag first, then fall back to
    # the loop_id alone, then to the function letters.
    new_inst: list[Instrument] = []
    matched_inst = 0
    for inst in vision.instruments:
        near = _bbox_center(inst.bbox) if inst.bbox else (
            (cx_canvas, cy_canvas) if cx_canvas else None
        )
        match = _best_match(inst.tag, ocr_blocks, near=near)
        if match is None and getattr(inst, "loop_id", None):
            # DIN: bottom row of the bubble carries just the loop_id.
            match = _best_match(inst.loop_id, ocr_blocks, near=near, max_distance=1)
        if match is None and getattr(inst, "function", None):
            # Top row of the bubble carries just the function letters.
            match = _best_match(inst.function, ocr_blocks, near=near, max_distance=0)
        if match:
            inflated = _inflate(match.bbox, dx=12, dy=12)
            new_inst.append(replace(inst, bbox=inflated))
            matched_inst += 1
            events.append({
                "stage": "fusion_match_instrument",
                "detail": f"{inst.tag} → bubble bbox {tuple(round(v, 1) for v in inflated)}",
                "elapsed_s": 0.0,
                "extra": {"tag": inst.tag, "ocr_text": match.text, "confidence": round(match.confidence, 1)},
            })
        else:
            new_inst.append(inst)
            events.append({
                "stage": "fusion_match_instrument",
                "detail": f"{inst.tag} → no OCR refinement",
                "elapsed_s": 0.0,
                "extra": {"tag": inst.tag},
            })

    # Lines — find OCR blocks whose normalised text begins with the
    # normalised line_no; polyline through their centres in reading order.
    new_lines: list[Line] = []
    matched_ln = 0
    for line in vision.lines:
        n_no = _normalize(line.line_no)
        hits = [b for b in ocr_blocks if _normalize(b.text).startswith(n_no[:8])]
        if hits:
            hits_sorted = sorted(hits, key=lambda b: (b.bbox[0], b.bbox[1]))
            geom = tuple(_bbox_center(b.bbox) for b in hits_sorted)
            new_lines.append(replace(line, geometry=geom))
            matched_ln += 1
            events.append({
                "stage": "fusion_match_line",
                "detail": f"{line.line_no} → polyline through {len(geom)} OCR labels",
                "elapsed_s": 0.0,
                "extra": {"line_no": line.line_no, "n_pts": len(geom)},
            })
        else:
            new_lines.append(line)
            events.append({
                "stage": "fusion_match_line",
                "detail": f"{line.line_no} → no OCR labels matched (kept Vision endpoints)",
                "elapsed_s": 0.0,
                "extra": {"line_no": line.line_no},
            })

    fused = ExtractionResult(
        drawing_id=vision.drawing_id,
        drawing_type=vision.drawing_type,
        title=vision.title,
        drawing_no=vision.drawing_no,
        equipment=tuple(new_eq),
        instruments=tuple(new_inst),
        lines=tuple(new_lines),
        connections=vision.connections,
    )
    return FusionResult(
        extraction=fused,
        events=tuple(events),
        matched_equipment=matched_eq,
        matched_instruments=matched_inst,
        matched_lines=matched_ln,
    )
