"""Sonnet 4.6 line-verifier sub-agent.

Pattern: Vision (Opus 4.8) extracts the full P&ID. Then this verifier
takes the **image + the OCR-confirmed line candidates + the Vision
line list** and produces a corrected line list — adding any OCR
candidate that Vision missed, removing any Vision line that the OCR
pass cannot confirm anywhere in the drawing.

The verifier never sees the ground truth. It is a *generic*
self-check pass: "given two views of the same drawing (Vision + OCR),
agree on the canonical line list".

Generic — no drawing-id branches, no GT lookups.
"""
from __future__ import annotations

import io
import json
import re
from typing import Sequence

from PIL import Image
from strands import Agent

from backend.agents.line_refinement import _normalise, _LINE_NO_RE
from backend.schemas import ExtractionResult, Line
from backend.strands_models import secondary_model


SYSTEM = """You are a careful P&ID line-number verifier. Your only job
is to produce the FINAL canonical list of pipe line numbers visible on
the drawing.

You receive:
  1. The drawing image
  2. OCR_LINES — line-number strings that Textract recognised on the
     image (verbatim, may contain noise — partial labels, cropped
     text, scanner artefacts).
  3. VISION_LINES — the line list extracted by an upstream Vision
     agent (correct topology, but punctuation may be slightly off).

Output rules:
  - Return JSON: {"lines": [{"line_no": "...", "size": "...",
                             "service": "...", "spec": "...",
                             "from_tag": null, "to_tag": null}]}
  - Each `line_no` MUST be a real line label visible on the drawing.
    Cross-check between OCR_LINES and VISION_LINES — include a label
    only if you can see it in the image.
  - Copy `line_no` byte-for-byte from whichever source has the cleanest
    form. Prefer OCR_LINES when it agrees with the image; prefer
    VISION_LINES when OCR has obvious noise (truncated, half-words).
  - Pull `size`/`service`/`spec` out of the line_no string itself
    (the grammar is `<size>"-<SERVICE>-<NUM>-<SPEC>`).
  - Set `from_tag`, `to_tag` to null — the orchestrator wires those
    later.
  - **Occlusion handling**: If the image has a black/white rectangle
    covering part of a line label, look at what is still visible on
    either side of the occlusion. Reconstruct the most likely full
    line_no by combining: (a) the partially-visible characters in the
    image, (b) any matching OCR_LINES candidate, (c) sequence
    inference from neighbouring line numbers. Add the reconstructed
    line — do not skip it.
  - **OCR coverage check (CRITICAL)**: Walk through OCR_LINES one by
    one. For EACH OCR candidate, decide whether you can confirm it
    on the drawing. If yes, it MUST appear in your output `lines`
    list. Do not omit a high-confidence OCR label just because the
    Vision agent didn't include it — that's the most common error
    mode this verifier exists to fix.
  - DO NOT produce any line that you cannot verify on the drawing.
  - DO NOT collapse two distinct line numbers into one. If two
    different labels appear (e.g. one with -CS spec and one with -SS
    spec), output BOTH.
  - Reply with ONLY the JSON object — no fences, no commentary."""


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


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


def _image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def verify_lines(
    image: Image.Image,
    extraction: ExtractionResult,
    ocr_candidates: Sequence[str],
) -> tuple[ExtractionResult, dict]:
    """Run the line-verifier and return a refined ExtractionResult.

    On any error the original extraction is returned unchanged so the
    pipeline never breaks because of an extra agent.
    """
    if not ocr_candidates and not extraction.lines:
        return extraction, {"verifier_used": False, "reason": "no input"}

    ocr_block = "\n".join(f"  - {c}" for c in sorted(set(ocr_candidates)))
    vision_block = "\n".join(
        f"  - {l.line_no}" for l in extraction.lines
    ) or "  (none)"
    user_text = (
        f"OCR_LINES (Textract):\n{ocr_block or '  (none)'}\n\n"
        f"VISION_LINES (Vision agent):\n{vision_block}\n\n"
        "Produce the final canonical line list."
    )
    message = [
        {"image": {"format": "png", "source": {"bytes": _image_to_bytes(image)}}},
        {"text": user_text},
    ]
    try:
        agent = Agent(
            model=secondary_model(),
            system_prompt=SYSTEM,
            callback_handler=None,
        )
        result = agent(message)
        parsed = _parse_json(_agent_text(result))
    except Exception as exc:  # noqa: BLE001
        return extraction, {
            "verifier_used": False, "reason": f"agent failed: {exc!r}",
        }

    raw_lines = parsed.get("lines", [])
    new_lines: list[Line] = []
    for entry in raw_lines:
        if not isinstance(entry, dict):
            continue
        line_no = str(entry.get("line_no", "")).strip()
        if not line_no:
            continue
        # Try to recover size/service/spec if the verifier omitted them.
        size = entry.get("size")
        service = entry.get("service")
        spec = entry.get("spec")
        if not (size and service and spec):
            m = _LINE_NO_RE.search(line_no)
            if m:
                size = size or f'{m.group("size")}"'
                service = service or m.group("service")
                spec = spec or m.group("spec")
        new_lines.append(Line(
            line_no=line_no,
            size=size,
            service=service,
            spec=spec,
            from_tag=None,
            to_tag=None,
        ))
    if not new_lines:
        return extraction, {
            "verifier_used": True, "reason": "verifier produced empty list",
        }

    # Re-attach from_tag / to_tag from the original Vision lines when we
    # can match by normalised line_no — the verifier is told to leave
    # those null so it focuses on text fidelity.
    by_norm = {_normalise(l.line_no): l for l in extraction.lines}
    enriched: list[Line] = []
    for l in new_lines:
        match = by_norm.get(_normalise(l.line_no))
        if match:
            enriched.append(Line(
                line_no=l.line_no,
                size=l.size or match.size,
                service=l.service or match.service,
                spec=l.spec or match.spec,
                from_tag=match.from_tag,
                to_tag=match.to_tag,
                geometry=match.geometry,
            ))
        else:
            enriched.append(l)

    from dataclasses import replace as _replace
    return (
        _replace(extraction, lines=tuple(enriched)),
        {
            "verifier_used": True,
            "before_count": len(extraction.lines),
            "after_count": len(enriched),
            "ocr_candidates": len(ocr_candidates),
        },
    )
