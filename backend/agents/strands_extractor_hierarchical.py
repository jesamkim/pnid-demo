"""Hierarchical multi-agent extraction.

Pipeline:

    1. Zone Scout  (Sonnet 4.6, 1 call)  -> N process zones
    2. Zone Specialist (Opus 4.8, N parallel calls) -> N partial extractions
    3. Stitcher  (deterministic dedup + bbox shift) -> single ExtractionResult

This is opt-in via the `PNID_HIERARCHICAL=1` env flag (default OFF so
production behaviour is preserved). The orchestrator calls this in
place of `extract_tiled` when the flag is set AND the image is large
enough to benefit (≥ 4000 px on the long edge).
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Any

from PIL import Image

from backend.agents.conventions import DEFAULT as DEFAULT_CONVENTION
from backend.agents.strands_extractor import extract_from_image
from backend.agents.strands_zone_scout import (
    Zone,
    crop_zone,
    scout_zones,
)
from backend.schemas import (
    Connection,
    Equipment,
    ExtractionResult,
    Instrument,
    Line,
)


def hierarchical_enabled() -> bool:
    return os.getenv("PNID_HIERARCHICAL", "0").strip() == "1"


def should_run_hierarchical(image: Image.Image, threshold_px: int = 4000) -> bool:
    """Hierarchical pays off only on big drawings; small ones do better
    with a single Vision call."""
    return max(image.size) >= threshold_px


def _shift_bbox(
    bbox: tuple[float, float, float, float] | None,
    offset: tuple[int, int],
) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    dx, dy = offset
    x1, y1, x2, y2 = bbox
    return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)


def _shift_geometry(
    geom: tuple[tuple[float, float], ...] | None,
    offset: tuple[int, int],
) -> tuple[tuple[float, float], ...] | None:
    if not geom:
        return None
    dx, dy = offset
    return tuple((p[0] + dx, p[1] + dy) for p in geom)


def _shift_extraction(extraction: ExtractionResult, offset: tuple[int, int]) -> ExtractionResult:
    """Map every spatial field from zone-local coords back to page coords."""
    eq = tuple(replace(e, bbox=_shift_bbox(e.bbox, offset)) for e in extraction.equipment)
    inst = tuple(replace(i, bbox=_shift_bbox(i.bbox, offset)) for i in extraction.instruments)
    lines = tuple(
        replace(l, geometry=_shift_geometry(l.geometry, offset))
        for l in extraction.lines
    )
    return replace(extraction, equipment=eq, instruments=inst, lines=lines)


def _dedup_equipment(
    items: list[Equipment],
) -> tuple[Equipment, ...]:
    """Equipment tags are usually globally unique. Keep the first sighting,
    but if a later one carries a bbox while the first didn't, prefer the
    later (more grounded) record."""
    by_tag: dict[str, Equipment] = {}
    for e in items:
        prev = by_tag.get(e.tag)
        if prev is None:
            by_tag[e.tag] = e
            continue
        if prev.bbox is None and e.bbox is not None:
            by_tag[e.tag] = e
        # otherwise keep the earlier one (zone order is deterministic)
    return tuple(by_tag.values())


def _dedup_instruments(items: list[Instrument]) -> tuple[Instrument, ...]:
    by_tag: dict[str, Instrument] = {}
    for i in items:
        prev = by_tag.get(i.tag)
        if prev is None:
            by_tag[i.tag] = i
            continue
        # Prefer the one that has located_on filled
        if not prev.located_on and i.located_on:
            by_tag[i.tag] = i
        elif prev.bbox is None and i.bbox is not None:
            by_tag[i.tag] = i
    return tuple(by_tag.values())


def _dedup_lines(items: list[Line]) -> tuple[Line, ...]:
    by_no: dict[str, Line] = {}
    for l in items:
        prev = by_no.get(l.line_no)
        if prev is None:
            by_no[l.line_no] = l
            continue
        if not prev.geometry and l.geometry:
            by_no[l.line_no] = l
    return tuple(by_no.values())


def _dedup_connections(items: list[Connection]) -> tuple[Connection, ...]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Connection] = []
    for c in items:
        key = (c.from_tag, c.to_tag, c.type)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return tuple(out)


def _extract_one_zone(
    image: Image.Image,
    zone: Zone,
    drawing_id: str,
    line_candidates: tuple[str, ...],
    convention,
) -> tuple[ExtractionResult, dict[str, Any], tuple[int, int]]:
    """Crop + Vision sub-agent for a single zone."""
    cropped, offset = crop_zone(image, zone)
    hint = (
        f"Zone-focused extraction. This crop covers: {zone.topic}. "
        "Extract every visible equipment / instrument / line within "
        "this crop only — items outside the crop will be picked up by "
        "other zone agents."
    )
    extraction, meta = extract_from_image(
        cropped,
        drawing_id=drawing_id,
        context_hint=hint,
        line_candidates=line_candidates,
        convention=convention,
    )
    shifted = _shift_extraction(extraction, offset)
    return shifted, meta, offset


def extract_hierarchical(
    image: Image.Image,
    drawing_id: str,
    *,
    line_candidates: tuple[str, ...] = (),
    convention=None,
    max_workers: int = 3,
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Run the scout, fan out one Vision sub-agent per zone, stitch.

    Returns (extraction, meta). `meta` includes `zones`, `zones_run`,
    and per-zone token usage. If the scout yields zero zones, falls
    back to a single full-image Vision call (caller may choose to hand
    off to `extract_tiled` instead).
    """
    if convention is None:
        convention = DEFAULT_CONVENTION
    started = time.time()

    zones, scout_meta = scout_zones(image)
    if not zones:
        # Scout failed; fall back to single-shot. Caller has already
        # validated that the image is "big" so this is rare.
        extraction, sub_meta = extract_from_image(
            image, drawing_id=drawing_id,
            line_candidates=line_candidates,
            convention=convention,
        )
        return extraction, {
            "mode": "hierarchical_fallback_single",
            "scout": scout_meta,
            "elapsed_s": round(time.time() - started, 2),
            **sub_meta,
        }

    # Run zones in priority order so the safety-critical zones land in
    # the merged extraction first (their dedup wins ties).
    zones_sorted = sorted(zones, key=lambda z: 0 if z.priority == "high" else 1)

    eq_all: list[Equipment] = []
    inst_all: list[Instrument] = []
    lines_all: list[Line] = []
    conn_all: list[Connection] = []
    zone_metas: list[dict[str, Any]] = []
    drawing_type = "P&ID"
    title: str | None = None
    drawing_no: str | None = None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _extract_one_zone, image, z, drawing_id,
                line_candidates, convention,
            ): z
            for z in zones_sorted
        }
        for f in as_completed(futures):
            z = futures[f]
            try:
                extraction, meta, offset = f.result()
            except Exception as exc:  # noqa: BLE001
                zone_metas.append({
                    "topic": z.topic, "priority": z.priority,
                    "error": repr(exc),
                })
                continue
            eq_all.extend(extraction.equipment)
            inst_all.extend(extraction.instruments)
            lines_all.extend(extraction.lines)
            conn_all.extend(extraction.connections)
            if extraction.title and not title:
                title = extraction.title
            if extraction.drawing_no and not drawing_no:
                drawing_no = extraction.drawing_no
            zone_metas.append({
                "topic": z.topic, "priority": z.priority,
                "offset": list(offset),
                "eq": len(extraction.equipment),
                "inst": len(extraction.instruments),
                "lines": len(extraction.lines),
                "input_tokens": meta.get("input_tokens", 0),
                "output_tokens": meta.get("output_tokens", 0),
            })

    merged = ExtractionResult(
        drawing_id=drawing_id,
        drawing_type=drawing_type,
        title=title,
        drawing_no=drawing_no,
        equipment=_dedup_equipment(eq_all),
        instruments=_dedup_instruments(inst_all),
        lines=_dedup_lines(lines_all),
        connections=_dedup_connections(conn_all),
    )
    return merged, {
        "mode": "hierarchical",
        "scout": scout_meta,
        "zones": [{"topic": z.topic, "priority": z.priority,
                   "bbox_norm": list(z.bbox_norm)} for z in zones],
        "zones_run": zone_metas,
        "elapsed_s": round(time.time() - started, 2),
        "input_tokens": sum(m.get("input_tokens", 0) for m in zone_metas),
        "output_tokens": sum(m.get("output_tokens", 0) for m in zone_metas),
    }
