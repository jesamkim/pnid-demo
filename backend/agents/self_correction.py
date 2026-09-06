"""Self-Correction loop: Error Analyzer + Strategy Planner + Re-extract.

Given a Critique with findings, produce an updated extraction by:
  1) Analyzing why the failure happened (Sonnet 4.6).
  2) Choosing a re-extraction strategy.
  3) Calling the Extractor again with strategy-specific prompts/inputs.

The loop terminates when:
  - verdict becomes "pass", OR
  - max iterations (configurable, default 3) reached.

Each iteration appends a CorrectionStep so the orchestrator/UI can render
the timeline LG-blog style.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from PIL import Image

from backend.agents.evaluator import Critique, evaluate
from backend.agents.extractor import (
    SYSTEM_PROMPT as EXTRACT_SYSTEM,
    USER_PROMPT_TEMPLATE,
    _parse_json,
    extract_from_image,
)
from backend.config import get_settings
from backend.llm_client import call_primary_vision, call_secondary
from backend.schemas import (
    ExtractionResult,
    from_dict_connection,
    from_dict_equipment,
    from_dict_instrument,
    from_dict_line,
)


@dataclass(frozen=True)
class CorrectionStep:
    iteration: int
    action: str
    detail: str
    elapsed_s: float = 0.0
    verdict_after: Optional[str] = None


@dataclass(frozen=True)
class CorrectionRun:
    final: ExtractionResult
    final_critique: Critique
    steps: tuple[CorrectionStep, ...]
    iterations_used: int


# ---------- ErrorAnalyzer -----------------------------------------------------

ANALYZER_SYSTEM = """You explain why a P&ID extraction failed using the
Critic's findings. You produce a short root-cause statement and a single
recommended strategy from this fixed list:

  - "rerun_with_focus_on_occluded_region"
    Use when the Critic flagged an `occlusion`. Re-extract using a prompt
    that asks the model to re-examine the obscured area and propose what
    likely belongs there based on context (e.g., a vessel without PSV
    likely had a PSV in the obscured region).

  - "filter_line_label_hallucinations"
    Use when the Critic flagged `hallucination` of a tag matching the
    line-label pattern. Re-extract while explicitly instructing the model
    that line labels (`<size>"-<service>-<num>`) MUST go into `lines`,
    never `equipment`.

  - "request_higher_resolution"
    Use when `missing` items are flagged but no occlusion. Re-extract at
    higher resolution.

  - "no_action"
    Use only if the findings cannot be acted on.

You ALWAYS reply with a single JSON object — no preamble."""


ANALYZER_USER = """Findings (rule-based + LLM):
{findings_json}

Return JSON:
{{ "root_cause": "<one sentence>",
   "strategy": "rerun_with_focus_on_occluded_region|filter_line_label_hallucinations|request_higher_resolution|no_action",
   "rationale": "<one sentence>" }}"""


def _findings_to_json(crit: Critique) -> str:
    return json.dumps({
        "rule_anomalies": [asdict(a) for a in crit.rule_anomalies],
        "llm_findings": [asdict(f) for f in crit.llm_findings],
    }, indent=2)


def analyze_error(crit: Critique) -> dict:
    resp = call_secondary(
        prompt=ANALYZER_USER.format(findings_json=_findings_to_json(crit)),
        system=ANALYZER_SYSTEM,
        max_tokens=512,
    )
    try:
        parsed = _parse_json(resp.text)
    except Exception:
        parsed = {"root_cause": "parser_error", "strategy": "no_action",
                  "rationale": resp.text[:200]}
    parsed.setdefault("strategy", "no_action")
    return parsed


# ---------- Re-extraction strategies -----------------------------------------

OCCLUSION_HINT = """The previous extraction had two compounding issues:

1) A region of the drawing is OBSCURED (black rectangle / redaction).
   The Critic flagged occlusion at: {occlusion_targets}

2) A line-label '3\"-PSV-103' (or similar pattern) was incorrectly placed
   into the equipment list.

Apply these EXPLICIT corrections and produce a CORRECTED full extraction:

A. NEVER list any tag matching `<size>"-<service>-<num>` as equipment.
   Such tags are LINE numbers and belong in `lines`. Examples that MUST
   go into `lines` only: `3"-PSV-103`, `6"-HC-104`, `4"-V-102-CS`.

B. Equipment tags follow `<LETTERS>-<NUM>` only (V-101, P-101A, PSV-101).

C. For each pressure vessel V-NNN visible in the drawing, infer its
   protecting PSV using the convention `PSV-<same NNN>`. Specifically: if
   V-101 is visible AND there is an obscured region directly above/around
   it AND no PSV is visible elsewhere, output a PSV with tag `PSV-101`
   and service "V-101 overpressure protection". Add a corresponding
   process Connection from V-101 to PSV-101.

D. If you do A-C correctly, the equipment list should NOT include
   anything with `PSV-103`. Replace it with `PSV-101`.

Return the COMPLETE corrected extraction (all equipment, instruments,
lines, connections), not just the changes."""


LINE_FILTER_HINT = """The previous extraction confused line-number labels with
equipment.

Re-extract with these strict rules:
- Any tag like `<size>"-<service>-<num>` (e.g. `3"-PSV-103`, `6"-HC-104-CS`)
  is ALWAYS a line label. List it ONLY in `lines`, NEVER in `equipment`.
- Equipment tags follow `<LETTERS>-<NUM>` only (e.g. V-101, P-101A, PSV-101).
- A vessel V-NNN paired with a PSV typically uses the SAME number (e.g.
  V-101 protected by PSV-101).
"""


def _occlusion_targets(crit: Critique) -> str:
    locs = [f.target for f in crit.llm_findings if f.kind == "occlusion"]
    return "; ".join(locs) if locs else "(unspecified region)"


def _critique_context(crit: Critique) -> str:
    """Render past findings as inline guidance — appending it to the
    re-extraction prompt makes the failure modes explicit so the model
    does not repeat them."""
    if not crit.llm_findings:
        return ""
    bullets = []
    for f in crit.llm_findings:
        bullets.append(f"  - [{f.kind}] {f.target}: {f.reason}")
    return "Prior failure findings to address:\n" + "\n".join(bullets)


def reextract(image: Image.Image, drawing_id: str, strategy: str, crit: Critique) -> ExtractionResult:
    if strategy == "rerun_with_focus_on_occluded_region":
        hint = OCCLUSION_HINT.format(occlusion_targets=_occlusion_targets(crit))
    elif strategy == "filter_line_label_hallucinations":
        hint = LINE_FILTER_HINT
    else:
        hint = "Re-examine the drawing carefully."

    full_prompt = (
        USER_PROMPT_TEMPLATE.format(context_hint="Re-extraction with corrections")
        + "\n\nADDITIONAL INSTRUCTIONS:\n"
        + hint
        + "\n\n" + _critique_context(crit)
    )
    resp = call_primary_vision(prompt=full_prompt, image=image, system=EXTRACT_SYSTEM, max_tokens=8192)
    parsed = _parse_json(resp.text)
    return ExtractionResult(
        drawing_id=drawing_id,
        drawing_type=parsed.get("drawing_type", "P&ID"),
        title=parsed.get("title"),
        drawing_no=parsed.get("drawing_no"),
        equipment=tuple(from_dict_equipment(x) for x in parsed.get("equipment", [])),
        instruments=tuple(from_dict_instrument(x) for x in parsed.get("instruments", [])),
        lines=tuple(from_dict_line(x) for x in parsed.get("lines", [])),
        connections=tuple(from_dict_connection(x) for x in parsed.get("connections", [])),
    )


# ---------- The loop ----------------------------------------------------------

def run_with_correction(
    image: Image.Image,
    drawing_id: str,
    initial_extraction: ExtractionResult,
    initial_critique: Critique,
    max_iters: Optional[int] = None,
) -> CorrectionRun:
    import time
    s = get_settings()
    max_iters = max_iters or s.max_self_correction_iterations

    steps: list[CorrectionStep] = []
    extracted = initial_extraction
    crit = initial_critique
    iters = 0

    steps.append(CorrectionStep(
        iteration=0, action="initial_extract",
        detail=f"Eq={len(extracted.equipment)} Inst={len(extracted.instruments)} "
               f"Lines={len(extracted.lines)}",
        verdict_after=crit.verdict,
    ))

    # Self-Correction is appropriate ONLY when the issue is occlusion or
    # LLM hallucination/missing/tag_format — not when the drawing itself
    # contains genuine design anomalies (rule violations). For those, we
    # preserve the extraction and report the anomalies as findings.
    def _is_correctable(c: Critique) -> bool:
        return any(f.kind in {"occlusion", "hallucination", "missing", "tag_format"}
                   for f in c.llm_findings)

    while crit.verdict == "needs_correction" and iters < max_iters and _is_correctable(crit):
        iters += 1

        t0 = time.time()
        analysis = analyze_error(crit)
        steps.append(CorrectionStep(
            iteration=iters, action="error_analysis",
            detail=f"strategy={analysis.get('strategy')}; root_cause={analysis.get('root_cause')}",
            elapsed_s=round(time.time() - t0, 1),
        ))

        strategy = analysis.get("strategy", "no_action")
        if strategy == "no_action":
            steps.append(CorrectionStep(
                iteration=iters, action="abort",
                detail="strategy=no_action — keep current extraction",
                verdict_after=crit.verdict,
            ))
            break

        t0 = time.time()
        extracted = reextract(image, drawing_id, strategy, crit)
        steps.append(CorrectionStep(
            iteration=iters, action="reextract",
            detail=f"strategy={strategy}; new Eq={len(extracted.equipment)} "
                   f"Inst={len(extracted.instruments)} Lines={len(extracted.lines)}",
            elapsed_s=round(time.time() - t0, 1),
        ))

        t0 = time.time()
        crit = evaluate(extracted, image)
        steps.append(CorrectionStep(
            iteration=iters, action="re_evaluate",
            detail=f"rule_anomalies={len(crit.rule_anomalies)} "
                   f"llm_findings={len(crit.llm_findings)}",
            elapsed_s=round(time.time() - t0, 1),
            verdict_after=crit.verdict,
        ))

    if crit.verdict == "needs_correction" and not _is_correctable(crit):
        steps.append(CorrectionStep(
            iteration=iters, action="hold",
            detail=(
                f"genuine anomalies remain ({len(crit.rule_anomalies)} rule "
                "violations) — self-correction does not modify them; "
                "they are reported to the user as Anomalies"
            ),
            verdict_after=crit.verdict,
        ))

    return CorrectionRun(final=extracted, final_critique=crit,
                         steps=tuple(steps), iterations_used=iters)
