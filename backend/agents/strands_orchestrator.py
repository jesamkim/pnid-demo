"""End-to-end pipeline using Strands Agents.

Sequence: render -> extract -> evaluate -> self_correct (optional) -> finalize.
Emits ProgressEvent objects so the UI/WebSocket can render the LG-blog
agentic timeline in real time.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from backend.agents.convention_detector import detect_convention
from backend.agents.conventions import DEFAULT as DEFAULT_CONVENTION
from backend.agents.strands_evaluator import Critique, evaluate
from backend.agents.strands_extractor import extract_from_image
from backend.agents.strands_fusion import fuse
from backend.agents.strands_ocr import detect_text_blocks
from backend.agents.strands_self_correction import (
    CorrectionRun,
    run_with_correction,
)
from backend.config import get_settings
from backend.isa_validator import validate
from backend.schemas import Anomaly, ExtractionResult
from backend.tools.image_normalize import load_normalized
from backend.tools.pdf_renderer import render_page  # noqa: F401 (kept for back-compat)


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    detail: str
    elapsed_s: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    drawing_id: str
    extraction: ExtractionResult
    critique: Critique
    correction: Optional[CorrectionRun]
    anomalies: tuple[Anomaly, ...]
    events: tuple[ProgressEvent, ...]
    total_elapsed_s: float


ProgressCallback = Callable[[ProgressEvent], None]


def _emit(events: list[ProgressEvent], on_progress: Optional[ProgressCallback], evt: ProgressEvent) -> None:
    events.append(evt)
    if on_progress:
        on_progress(evt)


def run_pipeline(
    pdf_path: Path | str,
    drawing_id: str,
    page: int = 0,
    dpi: int = 200,
    on_progress: Optional[ProgressCallback] = None,
) -> PipelineResult:
    s = get_settings()
    events: list[ProgressEvent] = []
    started = time.time()

    t0 = time.time()
    # Image-first pipeline: every input (synthetic PDF / uploaded PDF /
    # uploaded PNG / NREL real sample) is normalised to a single PNG
    # cache via `image_normalize`. The viewer's `/api/drawings/{key}/
    # image` endpoint serves the same PNG, so bbox coordinates the
    # Vision agent emits land exactly on the pixels the user sees.
    image = load_normalized(pdf_path, page=page, dpi=dpi)
    _emit(events, on_progress, ProgressEvent(
        stage="render",
        detail=f"{Path(pdf_path).name} -> {image.size[0]}x{image.size[1]} @ {dpi}dpi (PNG)",
        elapsed_s=round(time.time() - t0, 2),
        # The frontend picks canvas dimensions out of the render event so
        # uploads / real-industry samples (which have no ground-truth
        # geometry) can still synthesize an overlay from the live
        # extraction bboxes.
        extra={"canvas_width": image.size[0], "canvas_height": image.size[1]},
    ))

    # Pre-extract OCR — runs BEFORE Vision so the Vision agent can be
    # primed with the verbatim line-number labels that Textract sees.
    # OCR is best-effort; Vision still runs even if Textract fails.
    ocr_blocks: tuple = ()
    line_candidates: tuple[str, ...] = ()
    t0 = time.time()
    try:
        ocr_blocks = detect_text_blocks(image)
        _emit(events, on_progress, ProgressEvent(
            stage="ocr_extract",
            detail=(
                f"Textract recovered {len(ocr_blocks)} text blocks; "
                f"line-grammar match deferred to convention detect"
            ),
            elapsed_s=round(time.time() - t0, 2),
            extra={"blocks": len(ocr_blocks)},
        ))
    except Exception as exc:  # noqa: BLE001
        _emit(events, on_progress, ProgressEvent(
            stage="ocr_extract",
            detail=f"OCR skipped: {exc!r}",
            elapsed_s=round(time.time() - t0, 2),
            extra={"blocks": 0, "error": str(exc)},
        ))

    # Detect which P&ID standard this drawing follows (ISA-5.1 vs DIN
    # EN 10628). The detector inspects the OCR text for prefixes,
    # service codes, and DIN flow markers; env var PNID_CONVENTION
    # forces a specific standard for testing.
    detection = detect_convention(ocr_blocks)
    convention = detection.convention
    _emit(events, on_progress, ProgressEvent(
        stage="convention_detect",
        detail=(
            f"{convention.display_name} — source={detection.source} "
            f"(isa={detection.isa_score} din={detection.din_score})"
        ),
        elapsed_s=0.0,
        extra={
            "name": convention.name,
            "source": detection.source,
            "isa_score": detection.isa_score,
            "din_score": detection.din_score,
        },
    ))

    # Now that we know the convention, scan OCR for line candidates
    # using its specific regex. Empty if OCR failed above.
    if ocr_blocks:
        from backend.agents.line_refinement import find_line_candidates
        line_candidates = tuple(
            find_line_candidates(
                ocr_blocks, line_no_regex=convention.line_no_regex,
            )
        )

    t0 = time.time()
    # Decompose very large images into overlapping tiles so each
    # Vision sub-call's output stays inside max_tokens. Below the
    # threshold we keep the single-shot path. This is the LG-blog
    # "패칭(patching)" step done by parallel Vision subagents.
    from backend.agents.strands_extractor_tiled import (
        extract_tiled,
        should_tile,
    )
    from backend.agents.strands_extractor_hierarchical import (
        extract_hierarchical,
        hierarchical_enabled,
        should_run_hierarchical,
    )
    use_hier = hierarchical_enabled() and should_run_hierarchical(image)
    if use_hier:
        extraction, meta = extract_hierarchical(
            image, drawing_id=drawing_id,
            line_candidates=line_candidates,
            convention=convention,
        )
        zones_run = meta.get("zones_run") or []
        extract_detail = (
            f"Eq={len(extraction.equipment)} Inst={len(extraction.instruments)} "
            f"Lines={len(extraction.lines)} Conn={len(extraction.connections)} "
            f"(hierarchical: {len(zones_run)} zones)"
        )
    elif should_tile(image):
        extraction, meta = extract_tiled(
            image, drawing_id=drawing_id,
            line_candidates=line_candidates,
            convention=convention,
        )
        extract_detail = (
            f"Eq={len(extraction.equipment)} Inst={len(extraction.instruments)} "
            f"Lines={len(extraction.lines)} Conn={len(extraction.connections)} "
            f"(tiled: {meta.get('tiles_succeeded', 0)}/{meta.get('tiles_used', 0)})"
        )
    else:
        extraction, meta = extract_from_image(
            image, drawing_id=drawing_id,
            line_candidates=line_candidates,
            convention=convention,
        )
        # If the OCR pass found materially more line candidates than
        # the Vision pass produced, retry Vision once. Generic — only
        # triggers when there's a measurable gap (≥4 missing) and only
        # for the single-shot path (tiled already runs N parallel
        # sub-calls).
        ocr_count = len(line_candidates)
        vision_count = len(extraction.lines)
        if ocr_count >= 4 and ocr_count - vision_count >= 4:
            from dataclasses import replace as _replace
            retry, retry_meta = extract_from_image(
                image, drawing_id=drawing_id,
                line_candidates=line_candidates,
                convention=convention,
                context_hint=(
                    "Standalone P&ID page (RETRY). The previous pass "
                    "likely missed several line numbers — be thorough."
                ),
            )
            # Union by canonical line_no — keep first occurrence's
            # metadata (from_tag/to_tag), append new ones.
            from backend.agents.line_refinement import _normalise
            seen = {_normalise(l.line_no) for l in extraction.lines}
            extra = [
                l for l in retry.lines
                if _normalise(l.line_no) not in seen
            ]
            if extra:
                extraction = _replace(
                    extraction,
                    lines=tuple(list(extraction.lines) + extra),
                )
                meta["retry_added_lines"] = len(extra)
        extract_detail = (
            f"Eq={len(extraction.equipment)} Inst={len(extraction.instruments)} "
            f"Lines={len(extraction.lines)} Conn={len(extraction.connections)}"
        )
    _emit(events, on_progress, ProgressEvent(
        stage="extract",
        detail=extract_detail,
        elapsed_s=round(time.time() - t0, 2),
        extra={"input_tokens": meta.get("input_tokens", 0),
               "output_tokens": meta.get("output_tokens", 0),
               "tiles_used": meta.get("tiles_used", 1),
               "ocr_hints_used": len(line_candidates)},
    ))

    # OCR-anchored line-number refinement — Vision sometimes returns a
    # slightly normalised line_no (drops the inch sign, lowercases the
    # service code). Textract sees the same drawing pixel-by-pixel and
    # gets punctuation right, so we use a Levenshtein-bounded swap
    # AFTER Vision but BEFORE Fusion. Generic — never references a
    # specific tag.
    if ocr_blocks:
        from backend.agents.line_refinement import refine_lines
        from backend.agents.strands_line_verifier import verify_lines
        from backend.agents.strands_zoom_lines import zoom_pass
        t0 = time.time()
        extraction, refine_stats = refine_lines(
            extraction, ocr_blocks,
            max_distance=2,
            add_unmatched_candidates=True,
            line_no_regex=convention.line_no_regex,
        )
        # Zoom-pass — crop the image to the OCR line-label region and
        # run a focused Vision call to recover lines the main pass
        # missed. N=2 measurement showed +0.006 stable gain over
        # verifier-only architecture (0.8795 vs 0.873 mean). Set
        # PNID_ZOOM_LINES=0 to opt out.
        if os.getenv("PNID_ZOOM_LINES", "1") != "0":
            extraction, zoom_stats = zoom_pass(
                image, drawing_id, extraction, ocr_blocks,
            )
        # Sonnet 4.6 line-verifier — final cross-check.
        extraction, verify_stats = verify_lines(
            image, extraction, line_candidates,
        )
        _emit(events, on_progress, ProgressEvent(
            stage="line_refine",
            detail=(
                f"OCR-anchored line refinement: "
                f"matched={refine_stats['matched']} "
                f"added={refine_stats['added']} "
                f"(of {refine_stats['candidates']} candidates)"
            ),
            elapsed_s=round(time.time() - t0, 2),
            extra=refine_stats,
        ))

    # Fusion — match OCR text to Vision tags; emit one event per match.
    t0 = time.time()
    if ocr_blocks:
        fusion = fuse(extraction, ocr_blocks, canvas=image.size)
        extraction = fusion.extraction
        for ev in fusion.events:
            _emit(events, on_progress, ProgressEvent(
                stage=ev["stage"],
                detail=ev["detail"],
                elapsed_s=0.0,
                extra=ev.get("extra", {}),
            ))
        _emit(events, on_progress, ProgressEvent(
            stage="fusion_done",
            detail=(
                f"matched eq={fusion.matched_equipment}/{len(extraction.equipment)} "
                f"inst={fusion.matched_instruments}/{len(extraction.instruments)} "
                f"line={fusion.matched_lines}/{len(extraction.lines)}"
            ),
            elapsed_s=round(time.time() - t0, 2),
        ))

    t0 = time.time()
    crit = evaluate(extraction, image)
    # Deterministic missing-line check — when OCR found materially
    # more line candidates than the final extraction kept, inject a
    # `missing` finding so the self-correction loop fires another
    # extraction iteration. Generic; never references a tag.
    if line_candidates:
        from backend.agents.line_refinement import _normalise as _norm_line
        from backend.agents.strands_evaluator import Critique, Finding
        from dataclasses import replace as _replace
        kept_norm = {_norm_line(l.line_no) for l in extraction.lines}
        missing_ocr = [c for c in line_candidates if _norm_line(c) not in kept_norm]
        if len(missing_ocr) >= 3:
            extra_finding = Finding(
                kind="missing",
                target=f"{len(missing_ocr)} OCR-confirmed line label(s)",
                reason=(
                    "OCR detected line numbers that the final extraction "
                    "does not include — the Vision pass may have skipped "
                    "labels in dense regions."
                ),
                evidence=", ".join(missing_ocr[:5]) +
                ("…" if len(missing_ocr) > 5 else ""),
            )
            crit = _replace(
                crit,
                llm_findings=tuple(list(crit.llm_findings) + [extra_finding]),
                verdict="needs_correction",
            )
    _emit(events, on_progress, ProgressEvent(
        stage="evaluate",
        detail=f"verdict={crit.verdict} rule_anomalies={len(crit.rule_anomalies)} "
               f"llm_findings={len(crit.llm_findings)}",
        elapsed_s=round(time.time() - t0, 2),
    ))

    correction: Optional[CorrectionRun] = None
    if crit.verdict == "needs_correction":
        t0 = time.time()
        correction = run_with_correction(
            image, drawing_id, extraction, crit,
            max_iters=s.max_self_correction_iterations,
        )
        for cs in correction.steps:
            _emit(events, on_progress, ProgressEvent(
                stage=f"self_correct_{cs.action}",
                detail=cs.detail,
                elapsed_s=cs.elapsed_s,
                extra={"iteration": cs.iteration,
                       "verdict_after": cs.verdict_after or ""},
            ))
        extraction = correction.final
        crit = correction.final_critique
        _emit(events, on_progress, ProgressEvent(
            stage="self_correct_done",
            detail=f"iterations={correction.iterations_used} final_verdict={crit.verdict}",
            elapsed_s=round(time.time() - t0, 2),
        ))

    # Post-extraction enrichment: Valve Scanner + Connection Stitcher.
    # These run after self-correction so they see the cleanest extraction.
    # Both use Opus 4.8 Vision for precise spatial reasoning.
    if use_hier:
        from backend.agents.strands_valve_scanner import scan_valves
        from backend.agents.strands_connection_stitcher import stitch_connections
        from backend.agents.strands_zone_scout import scout_zones as _scout

        t0 = time.time()
        # Reuse zones from the hierarchical extraction meta (avoid re-scouting)
        cached_zones_raw = meta.get("zones") if use_hier else None
        if cached_zones_raw:
            from backend.agents.strands_zone_scout import Zone as _Zone
            cached_zones = [
                _Zone(topic=z["topic"], bbox_norm=tuple(z["bbox_norm"]),
                      priority=z.get("priority", "normal"))
                for z in cached_zones_raw
            ]
        else:
            cached_zones, _ = _scout(image)
            cached_zones = list(cached_zones)

        extraction, valve_meta = scan_valves(image, extraction, zones=cached_zones)
        _emit(events, on_progress, ProgressEvent(
            stage="valve_scan",
            detail=f"found {valve_meta['valves_found']} new valves across {valve_meta['zones_scanned']} zones",
            elapsed_s=round(time.time() - t0, 2),
            extra=valve_meta,
        ))

        t0 = time.time()
        extraction, conn_meta = stitch_connections(image, extraction)
        _emit(events, on_progress, ProgressEvent(
            stage="connection_stitch",
            detail=f"added {conn_meta['added_after_dedup']} new connections (total {conn_meta['total_connections']})",
            elapsed_s=round(time.time() - t0, 2),
            extra=conn_meta,
        ))

    t0 = time.time()
    anomalies = validate(extraction, rules=convention.anomaly_rules)
    _emit(events, on_progress, ProgressEvent(
        stage="finalize",
        detail=f"anomalies={len(anomalies)} (convention={convention.name})",
        elapsed_s=round(time.time() - t0, 2),
    ))

    return PipelineResult(
        drawing_id=drawing_id,
        extraction=extraction,
        critique=crit,
        correction=correction,
        anomalies=anomalies,
        events=tuple(events),
        total_elapsed_s=round(time.time() - started, 2),
    )
