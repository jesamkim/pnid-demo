"""Strands Agent for P&ID extraction.

Encapsulates Vision-based JSON extraction using a Strands Agent + a single
tool that returns the parsed extraction. The tool wrapping is deliberately
thin — the Vision call goes through the model directly with image input,
since Strands handles image content blocks natively.
"""
from __future__ import annotations

import io
import json
import re
from typing import Any

from PIL import Image
from strands import Agent

from backend.agents.conventions import DEFAULT as DEFAULT_CONVENTION, Convention
from backend.schemas import (
    ExtractionResult,
    from_dict_connection,
    from_dict_equipment,
    from_dict_instrument,
    from_dict_line,
)
from backend.strands_models import primary_model


SYSTEM_PROMPT = """You are an expert P&ID (Piping and Instrumentation Diagram) reader
following ISA-5.1 conventions.

You ALWAYS reply with a single JSON object (no preamble, no fences) matching
this schema:

{
  "drawing_type": "P&ID",
  "title": <string or null>,
  "drawing_no": <string or null>,
  "equipment": [{ "tag": "...", "type": "vessel|pump|heat_exchanger|psv|tank|column|reactor|gate_valve|ball_valve|control_valve|filter|other", "service": <string or null> }],
  "instruments": [{ "tag": "...", "function": "PT|FT|LT|FIC|TIC|LIC|...", "loop_id": "...", "located_on": <equipment_tag, line_no, "panel" or null> }],
  "lines": [{ "line_no": "...", "size": "...", "service": "...", "spec": "...", "from_tag": <tag or null>, "to_tag": <tag or null> }],
  "connections": [{ "from_tag": "...", "to_tag": "...", "type": "process|signal|utility", "via_line": <line_no or null> }]
}

Tag conventions:
- Equipment: <LETTERS>-<NUM>, e.g. V-101, P-101A, PSV-101, GV-102.
- Instruments: ISA-5.1 function letters + loop number, e.g. PT-101, FT-201.
- Line numbers: <size>"-<service>-<num>-<spec>, e.g. 6\"-FG-101-CS.
- A tag like '3"-PSV-103' is a LINE NUMBER (size="3\\"" service="PSV"), NOT equipment.
- If two labels exist for the same line with different specs (e.g. -CS and -SS),
  list BOTH as separate Line entries.

LINE NUMBER FIDELITY RULES (very important — small mistakes here drop F1):

1. Copy line numbers VERBATIM from the drawing. Do not normalise,
   shorten, or "tidy". The exact characters that appear on the
   drawing — the inch sign, hyphens, casing, leading zeros — must
   appear in `line_no`.

2. The standard grammar is exactly:
       <size>"-<SERVICE>-<NUM>-<SPEC>
   where:
     <size>     = digits, optionally with a fraction (3, 6, 12, 1-1/2)
     "          = a literal ASCII double-quote (U+0022). NOT smart quote.
     <SERVICE>  = uppercase letters / digits, hyphens preserved
                  (FG, NGL, OVH, RFX, RBO, BTM, PSV, RCY, FLR, DRN,
                  LAM, RAM, MUH, SOR, CRD, EFF, ATM, VAC, NPH, KER,
                  DIE, VGO, SLW, MUW, FED, C3P, C4P, BTM, …). If the
                  drawing shows something not in this list, copy it
                  verbatim — do NOT replace with a "nearby" code.
     <NUM>      = the digits that appear on the label, including
                  leading characters (e.g. 101, 211, 305).
     <SPEC>     = a piping spec code such as CS, SS, GA, A106B.

3. Echo every character once and only once. Common mistakes to avoid:
     • dropping the inch sign  ("8-FG-101-CS"   ← WRONG)
     • merging hyphens         ("8\"FG101CS"     ← WRONG)
     • lowercase service       ("8\"-fg-101-cs"  ← WRONG)
     • inserting spaces        ("8\" - FG - 101 - CS" ← WRONG)
     • truncating to <num>     ("FG-101"         ← WRONG)
   The correct form for the example above is exactly:
       8"-FG-101-CS

4. If the drawing label is partially occluded, output what you can
   see, mark the unreadable segment with a question-mark wildcard
   (e.g. `8"-FG-???-CS`), and still return the entry — do not drop
   the line.

5. Each line label appears ONCE on the drawing. Output exactly one
   `lines[]` entry per distinct line_no. Do not invent extra lines.
"""


_IMG_BLOCK_RE = re.compile(r"^```[a-zA-Z]*\n?|\n?```\s*$")


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = _strip_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _image_to_bytes(img: Image.Image, fmt: str = "png") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt.upper())
    return buf.getvalue()


def _agent_text(result) -> str:
    """Extract text content from a Strands AgentResult.message."""
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


def _make_extractor_agent(convention: Convention = DEFAULT_CONVENTION) -> Agent:
    # callback_handler=None silences the default streaming print so the
    # JSON response doesn't leak to stdout in production.
    return Agent(model=primary_model(),
                 system_prompt=convention.extractor_system_prompt,
                 callback_handler=None)


def extract_from_image(
    image: Image.Image,
    drawing_id: str,
    context_hint: str = "Standalone P&ID page",
    line_candidates: tuple[str, ...] = (),
    convention: Convention = DEFAULT_CONVENTION,
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Run Strands Agent + Vision extraction and parse the JSON response.

    `line_candidates`: optional list of canonical line-number strings
    that an upstream OCR pass already detected on this image. Including
    them in the user prompt nudges Vision to (a) not miss those lines
    and (b) reproduce their punctuation verbatim. Generic — never
    references a specific drawing or tag. Empty list keeps the
    behaviour identical to the v15 path.
    """
    agent = _make_extractor_agent(convention)

    if line_candidates:
        # Cap at 50 to keep the prompt bounded on tile sub-calls.
        unique = sorted(set(line_candidates))[:50]
        ocr_hint = (
            "\n\nOCR LINE CANDIDATES (Textract already detected these line "
            "labels on this image — use them as hints, copy each label "
            "verbatim, and include every one that is actually visible "
            "on the drawing):\n  " + "\n  ".join(unique)
        )
    else:
        ocr_hint = ""

    user_text = (
        f"Drawing context: {context_hint}\n\n"
        "Extract every visible element of this P&ID into the JSON schema "
        "described in the system prompt. Return ONLY the JSON object."
        + ocr_hint
    )
    message = [
        {"image": {"format": "png", "source": {"bytes": _image_to_bytes(image)}}},
        {"text": user_text},
    ]

    result = agent(message)
    text = _agent_text(result)
    parsed = _parse_json(text)

    extraction = ExtractionResult(
        drawing_id=drawing_id,
        drawing_type=parsed.get("drawing_type", "P&ID"),
        title=parsed.get("title"),
        drawing_no=parsed.get("drawing_no"),
        equipment=tuple(from_dict_equipment(x) for x in parsed.get("equipment", [])),
        instruments=tuple(from_dict_instrument(x) for x in parsed.get("instruments", [])),
        lines=tuple(from_dict_line(x) for x in parsed.get("lines", [])),
        connections=tuple(from_dict_connection(x) for x in parsed.get("connections", [])),
    )

    metrics = getattr(result, "metrics", None)
    in_tok = out_tok = 0
    if metrics is not None and hasattr(metrics, "accumulated_usage"):
        usage = metrics.accumulated_usage or {}
        in_tok = int(usage.get("inputTokens", 0))
        out_tok = int(usage.get("outputTokens", 0))

    raw_meta = {
        "model_id": primary_model().get_config().get("model_id", ""),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "raw_text": text,
    }
    return extraction, raw_meta
