"""Orchestrator: end-to-end pipeline for one P&ID drawing.

Pipeline order matches LG-blog Agentic pattern:
  1. Render PDF -> image
  2. Extractor (Vision) -> initial ExtractionResult
  3. Evaluator (Rule + LLM Critic) -> Critique
  4. Self-Correction loop (only when correctable findings exist)
  5. Final ISA validation reports anomalies that should NOT be auto-corrected

Each stage emits a ProgressEvent so a UI/WebSocket can render the timeline.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PIL import Image

from backend.agents.evaluator import Critique, evaluate
from backend.agents.extractor import extract_from_image
from backend.agents.self_correction import CorrectionRun, run_with_correction
from backend.config import get_settings
from backend.isa_validator import validate
from backend.schemas import Anomaly, ExtractionResult
from backend.tools.pdf_renderer import render_page


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

    # 1) Render
    t0 = time.time()
    image = render_page(pdf_path, page=page, dpi=dpi)
    _emit(events, on_progress, ProgressEvent(
        stage="render",
        detail=f"{Path(pdf_path).name} -> {image.size[0]}x{image.size[1]} @ {dpi}dpi",
        elapsed_s=round(time.time() - t0, 2),
    ))

    # 2) Initial extract
    t0 = time.time()
    extraction, meta = extract_from_image(image, drawing_id=drawing_id)
    _emit(events, on_progress, ProgressEvent(
        stage="extract",
        detail=f"Eq={len(extraction.equipment)} Inst={len(extraction.instruments)} "
               f"Lines={len(extraction.lines)} Conn={len(extraction.connections)}",
        elapsed_s=round(time.time() - t0, 2),
        extra={"input_tokens": meta["input_tokens"], "output_tokens": meta["output_tokens"]},
    ))

    # 3) Evaluator
    t0 = time.time()
    crit = evaluate(extraction, image)
    _emit(events, on_progress, ProgressEvent(
        stage="evaluate",
        detail=f"verdict={crit.verdict} rule_anomalies={len(crit.rule_anomalies)} "
               f"llm_findings={len(crit.llm_findings)}",
        elapsed_s=round(time.time() - t0, 2),
    ))

    # 4) Self-correction (if applicable) — emits its own per-step events
    correction: Optional[CorrectionRun] = None
    if crit.verdict == "needs_correction":
        t0 = time.time()
        correction = run_with_correction(image, drawing_id, extraction, crit,
                                         max_iters=s.max_self_correction_iterations)
        for cs in correction.steps:
            _emit(events, on_progress, ProgressEvent(
                stage=f"self_correct_{cs.action}",
                detail=cs.detail,
                elapsed_s=cs.elapsed_s,
                extra={"iteration": cs.iteration, "verdict_after": cs.verdict_after or ""},
            ))
        extraction = correction.final
        crit = correction.final_critique
        _emit(events, on_progress, ProgressEvent(
            stage="self_correct_done",
            detail=f"iterations={correction.iterations_used} final_verdict={crit.verdict}",
            elapsed_s=round(time.time() - t0, 2),
        ))

    # 5) Final anomaly report
    t0 = time.time()
    anomalies = validate(extraction)
    _emit(events, on_progress, ProgressEvent(
        stage="finalize",
        detail=f"anomalies={len(anomalies)}",
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
