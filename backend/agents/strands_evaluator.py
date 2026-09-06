"""Strands Agent for the LLM Critic step.

Combines deterministic ISA rules (backend.isa_validator.validate) with a
Sonnet-4.6-backed Strands Agent that re-examines the source image plus the
extracted JSON and raises confident findings.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field

from PIL import Image
from strands import Agent

from backend.isa_validator import validate
from backend.schemas import Anomaly, ExtractionResult
from backend.strands_models import secondary_model


CRITIC_SYSTEM = """You are an extremely conservative P&ID reviewer.

You are given (a) the source drawing image and (b) a JSON extraction produced
by another agent. You ONLY raise findings when you are >95% confident there is
a clear, objective error. When in doubt, the finding is NOT raised.

You raise a finding ONLY in these four confident categories:

1) HALLUCINATION: AN EQUIPMENT entry (i.e., it appears in the `equipment`
   array in the JSON) whose tag matches the LINE-LABEL pattern
   `<size>"-<service>-<num>` (e.g. `3"-PSV-103`, `6"-HC-104`). Equipment tags
   MUST follow `<LETTERS>-<NUM>` like `V-101`, `P-101A`, `PSV-101`, `GV-102`.
   IMPORTANT: line entries (in the `lines` array) that follow the line-label
   pattern are CORRECT — those are NOT hallucinations.
2) MISSING: a clearly visible AND labeled symbol in the drawing that is
   completely absent from the JSON. You must point to its exact location.
3) TAG_FORMAT: a malformed tag (spaces, slashes, pipe-size syntax `"-`).
4) OCCLUSION: a region of the drawing is visibly OBSCURED — a black rectangle,
   a heavy redaction box, a torn corner, or a smudge — covering what would
   otherwise be a labeled symbol. When you see ANY occlusion, raise this
   finding regardless of whether the JSON appears correct.

DO NOT raise findings for type classification, naming-convention preferences,
minor metadata gaps, or subjective interpretations.

If you have ZERO confident findings AND no occlusion, set verdict to "pass"
with an empty findings list.

You ALWAYS reply with a single JSON object — no preamble, no fences:
{
  "findings": [
    {"kind": "hallucination|missing|tag_format|occlusion",
     "target": "<tag or short location>",
     "reason": "<one sentence>",
     "evidence": "<what you see in the drawing>"}
  ],
  "verdict": "pass|needs_correction"
}"""


_LINE_LIKE = re.compile(r'^\d+(?:/\d+)?"-')


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
    verdict: str
    raw_meta: dict = field(default_factory=dict)


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _parse_json(text: str) -> dict:
    cleaned = _strip_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


def _image_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _local_hallucination_check(r: ExtractionResult) -> list[Finding]:
    out: list[Finding] = []
    for e in r.equipment:
        if _LINE_LIKE.match(e.tag):
            out.append(Finding(
                kind="hallucination",
                target=e.tag,
                reason=f"Equipment tag {e.tag!r} matches the line-label pattern.",
                evidence="Line labels follow <size>-<service>-<num>-<spec>.",
            ))
    return out


def evaluate(extracted: ExtractionResult, image: Image.Image) -> Critique:
    rule_anom = validate(extracted)
    findings_local = _local_hallucination_check(extracted)

    extracted_json = json.dumps({
        "drawing_type": extracted.drawing_type,
        "title": extracted.title,
        "drawing_no": extracted.drawing_no,
        "equipment": [{"tag": e.tag, "type": e.type, "service": e.service} for e in extracted.equipment],
        "instruments": [{"tag": i.tag, "function": i.function, "loop_id": i.loop_id, "located_on": i.located_on} for i in extracted.instruments],
        "lines": [{"line_no": l.line_no, "from_tag": l.from_tag, "to_tag": l.to_tag, "spec": l.spec} for l in extracted.lines],
    }, indent=2)

    agent = Agent(model=secondary_model(), system_prompt=CRITIC_SYSTEM, callback_handler=None)
    message = [
        {"image": {"format": "png", "source": {"bytes": _image_bytes(image)}}},
        {"text": (
            f"Extracted JSON:\n```json\n{extracted_json}\n```\n\n"
            "Return JSON: {\"findings\": [...], \"verdict\": \"pass|needs_correction\"}.\n"
            "Respond with ONLY the JSON object."
        )},
    ]

    try:
        result = agent(message)
        text = _agent_text(result)
        parsed = _parse_json(text)
        llm_findings = tuple(
            Finding(
                kind=f.get("kind", "unknown"),
                target=f.get("target", ""),
                reason=f.get("reason", ""),
                evidence=f.get("evidence", ""),
            )
            for f in parsed.get("findings", [])
        )
    except Exception as e:
        llm_findings = (Finding(
            kind="critic_parse_error", target="", reason=str(e), evidence="",
        ),)

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
        raw_meta={"model_id": secondary_model().get_config().get("model_id", "")},
    )
