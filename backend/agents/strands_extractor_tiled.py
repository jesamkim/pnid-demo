"""Tile-based Vision subagent fan-out for very large drawings.

Why
---
A 7800-px-wide P&ID with 50+ equipment, 60+ instruments and 50+ lines
exceeds what a single Vision call can return inside the model's
max_tokens budget — Strands raises `MaxTokensReachedException` and
the run fails. Tiling the image into overlapping windows and running
each tile through its own Vision sub-agent keeps every sub-call's
output well below the limit, then a small fan-in step deduplicates
tags across the overlap and reassembles a single ExtractionResult.

This is the patching/decomposition step described in the LG ES tech
blog (Photo4 — "필요부분 패칭"). For our demo we keep the agent
boundary at *Vision only*; OCR + Fusion already operate on the full
image and don't need tiling because Textract handles big images.

Public contract
---------------
`extract_tiled(image, drawing_id, tile_size=3500, overlap=400) ->
ExtractionResult, meta`

  - Tile size 3500 + overlap 400 → for a 7800×3000 image we get a
    3×1 grid of ~3500 px tiles. Sub-call output is ~1/3 of the
    original, comfortably inside max_tokens.
  - Tag deduplication uses normalised tag string (e.g. "V-101" wins
    over "V101" if both appear; ties broken by larger bbox area).
  - Bbox coordinates are translated into the global image frame so
    downstream Fusion / overlay code doesn't change.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Any, Iterable

from PIL import Image

from backend.agents.strands_extractor import extract_from_image
from backend.schemas import (
    Connection,
    Equipment,
    ExtractionResult,
    Instrument,
    Line,
)
from backend.tools.pdf_renderer import Tile, tile_image


def should_tile(image: Image.Image, *, threshold_px: int = 5500) -> bool:
    """True if the image is large enough that a single Vision call
    risks max_tokens.

    Threshold = ~5500 px on the long edge. Below this we keep the
    1-shot extractor; above we fan out.
    """
    return max(image.size) >= threshold_px


def extract_tiled(
    image: Image.Image,
    drawing_id: str,
    *,
    tile_size: int = 3500,
    overlap: int = 400,
    max_workers: int = 3,
    context_hint: str = "Standalone P&ID page (tile)",
    line_candidates: tuple[str, ...] = (),
    convention=None,
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Fan out Vision extraction across overlapping tiles, fan in
    deduplicated results."""
    if convention is None:
        from backend.agents.conventions import DEFAULT as _DEFAULT_CONV
        convention = _DEFAULT_CONV
    started = time.time()
    tiles = tile_image(image, tile_size=tile_size, overlap=overlap)

    # Hand each tile to its own sub-agent in parallel. Strands agents
    # are stateless from the caller's POV, so plain ThreadPoolExecutor
    # is enough; each invocation gets its own BedrockModel instance.
    sub_results: list[tuple[Tile, ExtractionResult, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                _extract_one_tile, t, drawing_id, context_hint, line_candidates, convention,
            ): t
            for t in tiles
        }
        for f in as_completed(futures):
            tile = futures[f]
            try:
                ex, meta = f.result()
                sub_results.append((tile, ex, meta))
            except Exception as exc:  # noqa: BLE001
                # Tile failure is recoverable — we keep going with
                # whatever the other tiles produced.
                print(f"[extract_tiled] tile {tile.index} failed: {exc!r}")

    if not sub_results:
        raise RuntimeError("all Vision tiles failed")

    # Translate every tile's local bbox into image-global coords, then
    # merge with tag-aware dedup.
    eq_map: dict[str, Equipment] = {}
    inst_map: dict[str, Instrument] = {}
    line_map: dict[str, Line] = {}
    conn_set: set[tuple[str, str, str | None]] = set()
    connections: list[Connection] = []
    in_tok = out_tok = 0

    for tile, ex, meta in sub_results:
        in_tok += int(meta.get("input_tokens") or 0)
        out_tok += int(meta.get("output_tokens") or 0)

        for e in ex.equipment:
            _merge_equipment(eq_map, _shift_eq(e, tile))
        for i in ex.instruments:
            _merge_instrument(inst_map, _shift_inst(i, tile))
        for l in ex.lines:
            _merge_line(line_map, _shift_line(l, tile))
        for c in ex.connections:
            # Connection schema: from_tag / to_tag / type / via_line.
            # Dedup on the triple that matters across tile overlap.
            key = (c.from_tag, c.to_tag, c.type, c.via_line)
            if key in conn_set:
                continue
            conn_set.add(key)
            connections.append(c)

    merged = ExtractionResult(
        drawing_id=drawing_id,
        drawing_type="P&ID",
        title=None,
        drawing_no=None,
        equipment=tuple(eq_map.values()),
        instruments=tuple(inst_map.values()),
        lines=tuple(line_map.values()),
        connections=tuple(connections),
    )
    meta_out = {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "tiles_used": len(tiles),
        "tiles_succeeded": len(sub_results),
        "tile_elapsed_s": round(time.time() - started, 2),
    }
    return merged, meta_out


# ---------- internals -----------------------------------------------------


def _extract_one_tile(
    tile: Tile, drawing_id: str, context_hint: str,
    line_candidates: tuple[str, ...] = (),
    convention=None,
) -> tuple[ExtractionResult, dict[str, Any]]:
    if convention is None:
        from backend.agents.conventions import DEFAULT as _DEFAULT_CONV
        convention = _DEFAULT_CONV
    return extract_from_image(
        tile.image,
        drawing_id=drawing_id,
        context_hint=f"{context_hint} ({tile.x},{tile.y} {tile.width}×{tile.height})",
        line_candidates=line_candidates,
        convention=convention,
    )


def _shift_bbox(
    bbox: tuple[float, float, float, float] | None, tile: Tile,
) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    x1, y1, x2, y2 = bbox
    return (x1 + tile.x, y1 + tile.y, x2 + tile.x, y2 + tile.y)


def _shift_eq(e: Equipment, tile: Tile) -> Equipment:
    return replace(e, bbox=_shift_bbox(e.bbox, tile))


def _shift_inst(i: Instrument, tile: Tile) -> Instrument:
    return replace(i, bbox=_shift_bbox(i.bbox, tile))


def _shift_line(l: Line, tile: Tile) -> Line:
    geom = l.geometry
    if geom:
        geom = tuple((p[0] + tile.x, p[1] + tile.y) for p in geom)
    return replace(l, geometry=geom)


def _bbox_area(b: tuple[float, float, float, float] | None) -> float:
    if not b:
        return 0.0
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _merge_equipment(
    out: dict[str, Equipment], candidate: Equipment,
) -> None:
    key = candidate.tag.upper()
    incumbent = out.get(key)
    if incumbent is None:
        out[key] = candidate
        return
    # Tie-break: larger bbox area wins (less likely to be partial).
    if _bbox_area(candidate.bbox) > _bbox_area(incumbent.bbox):
        out[key] = candidate


def _merge_instrument(
    out: dict[str, Instrument], candidate: Instrument,
) -> None:
    key = candidate.tag.upper()
    incumbent = out.get(key)
    if incumbent is None or _bbox_area(candidate.bbox) > _bbox_area(incumbent.bbox):
        out[key] = candidate


def _merge_line(out: dict[str, Line], candidate: Line) -> None:
    key = candidate.line_no.upper()
    incumbent = out.get(key)
    if incumbent is None:
        out[key] = candidate
        return
    cand_pts = len(candidate.geometry or ())
    inc_pts = len(incumbent.geometry or ())
    # Prefer the version with more polyline points.
    if cand_pts > inc_pts:
        out[key] = candidate


__all__: Iterable[str] = ("should_tile", "extract_tiled")
