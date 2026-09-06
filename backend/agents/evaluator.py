"""Evaluator: combines deterministic ISA rules with an LLM Critic.

The deterministic part reuses backend.isa_validator. The LLM Critic
re-examines the extracted JSON together with the source image and flags:
  - Hallucinations: tags that look like ISA labels but aren't equipment
    (e.g. interpreting line label '3"-PSV-103' as an equipment tag).
  - Missing items: regions of the image that look like equipment/instruments
    but are absent from the extraction.
  - Schema deviations: malformed tags, inconsistent loop ids, etc.

Output: Critique with structured findings the orchestrator can route to the
Error Analyzer / Strategy Planner.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from PIL import Image

from backend.agents.extractor import _parse_json
from backend.isa_validator import validate
from backend.llm_client import call_secondary_vision
from backend.schemas import Anomaly, ExtractionResult


CRITIC_SYSTEM = """You are an extremely conservative P&ID reviewer.

You are given (a) the source drawing image and (b) a JSON extraction produced
by another agent. You ONLY raise findings when you are >95% confident there is
a clear, objective error. When in doubt, the finding is NOT raised.

You raise a finding ONLY in these four confident categories:

1) HALLUCINATION: an equipment entry whose tag matches the LINE-LABEL pattern
   `<size>"-<service>-<num>` (e.g. `3"-PSV-103`, `6"-HC-104`). Equipment tags
   MUST follow `<LETTERS>-<NUM>` like `V-101`, `P-101A`, `PSV-101`, `GV-102`.

2) MISSING: a clearly visible AND labeled symbol in the drawing that is
   completely absent from the JSON. You must be able to point to its exact
   location in the image.

3) TAG_FORMAT: a malformed tag — equipment whose tag contains spaces, slashes,
   or pipe-size syntax `"-`.

4) OCCLUSION: a region of the drawing is visibly OBSCURED — e.g. a black
   rectangle, a heavy redaction box, a torn corner, or a smudge — covering
   what would otherwise be a labeled symbol. When you see ANY such occlusion,
   raise this finding regardless of whether the JSON appears correct,
   because hidden symbols cannot be verified. Set `target` to the rough
   location ("top-left of vessel V-101", "near pump P-201", etc.) and
   `evidence` to the visual description.

DO NOT raise findings for:
- type classification questions ("is it a gate or ball valve?")
- borderline naming conventions ("'GV' is non-standard")
- minor metadata gaps (missing service text, null `to_tag`, missing line
  number suffix)
- subjective interpretation of the drawing

If you have ZERO confident findings AND no occlusion, set verdict to "pass"
with an empty findings list. This is the expected outcome for clean drawings.

You ALWAYS reply with a single JSON object — no preamble, no fences."""


CRITIC_USER = """Extracted JSON:
```json
{extracted}
```

Return JSON of this exact shape:

{{
  "findings": [
    {{ "kind": "hallucination|missing|tag_format",
       "target": "<tag or short description>",
       "reason": "<one sentence>",
       "evidence": "<what you see in the drawing>" }}
  ],
  "verdict": "pass|needs_correction"
}}

If `findings` is empty, set verdict to "pass". Otherwise "needs_correction".
Respond with ONLY the JSON object."""


@dataclass(frozen=True)
class Finding:
    kind: str
    target: str
    reason: str
    evidence: str = ""


@dataclass(frozen=True)
class Critique:
    rule_anomalies: tuple[Anomaly, ...]
    llm_findings: tuple[Finding, ...]
    verdict: str  # "pass" | "needs_correction"
    raw_meta: dict = field(default_factory=dict)


_LINE_LIKE = re.compile(r'^\d+(?:/\d+)?"-')


def _local_hallucination_check(r: ExtractionResult) -> list[Finding]:
    out: list[Finding] = []
    for e in r.equipment:
        if _LINE_LIKE.match(e.tag):
            out.append(Finding(
                kind="hallucination",
                target=e.tag,
                reason=f"Equipment tag {e.tag!r} looks like a line label, not an equipment tag.",
                evidence="Line labels follow the pattern <size>-<service>-<num>-<spec>.",
            ))
        # PSV-XXX where XXX > 200 is suspicious if the drawing follows 1xx numbering;
        # the tighter check is left to the LLM critic.
    return out


def evaluate(extracted: ExtractionResult, image: Image.Image) -> Critique:
    rule_anom = validate(extracted)
    findings_local = _local_hallucination_check(extracted)

    # LLM-based pass — uses Sonnet 4.6 (cheaper, faster) for critique.
    extracted_json = json.dumps({
        "drawing_type": extracted.drawing_type,
        "title": extracted.title,
        "drawing_no": extracted.drawing_no,
        "equipment": [{"tag": e.tag, "type": e.type, "service": e.service} for e in extracted.equipment],
        "instruments": [{"tag": i.tag, "function": i.function, "loop_id": i.loop_id, "located_on": i.located_on} for i in extracted.instruments],
        "lines": [{"line_no": l.line_no, "from_tag": l.from_tag, "to_tag": l.to_tag} for l in extracted.lines],
    }, indent=2)

    resp = call_secondary_vision(
        prompt=CRITIC_USER.format(extracted=extracted_json),
        image=image,
        system=CRITIC_SYSTEM,
        max_tokens=2048,
    )

    try:
        parsed = _parse_json(resp.text)
        llm_findings = tuple(
            Finding(
                kind=f.get("kind", "unknown"),
                target=f.get("target", ""),
                reason=f.get("reason", ""),
                evidence=f.get("evidence", ""),
            )
            for f in parsed.get("findings", [])
        )
        verdict = parsed.get("verdict", "pass")
    except Exception as e:
        llm_findings = (Finding(
            kind="critic_parse_error", target="", reason=str(e), evidence=resp.text[:200],
        ),)
        verdict = "needs_correction"

    # Only count llm_findings whose kind is one of the four confident categories.
    confident_kinds = {"hallucination", "missing", "tag_format", "occlusion"}
    confident_llm = tuple(f for f in llm_findings if f.kind in confident_kinds)
    all_findings = tuple(findings_local) + confident_llm
    if rule_anom or all_findings:
        verdict = "needs_correction"
    else:
        verdict = "pass"

    return Critique(
        rule_anomalies=rule_anom,
        llm_findings=all_findings,
        verdict=verdict,
        raw_meta={
            "model_id": resp.model_id,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "raw_text": resp.text,
        },
    )
