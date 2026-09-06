"""Vision Extractor agent: image -> structured P&ID JSON.

Uses Opus 4.8 for primary extraction. The prompt asks for STRICT JSON
matching backend.schemas.ExtractionResult. Failures parse-back to a Python
object that the orchestrator can validate and re-extract if needed.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from PIL import Image

from backend.llm_client import call_primary_vision, call_secondary_vision
from backend.schemas import (
    Connection, Equipment, ExtractionResult, Instrument, Line,
    from_dict_connection, from_dict_equipment, from_dict_instrument, from_dict_line,
)


SYSTEM_PROMPT = """You are an expert P&ID (Piping and Instrumentation Diagram) reader.
You analyze engineering drawings using ISA-5.1 conventions and extract structured data.

You ALWAYS respond with a single JSON object — no preamble, no Markdown fences,
just the JSON object that matches the schema below."""


USER_PROMPT_TEMPLATE = """Extract every visible element of this P&ID into JSON.

Schema (return EXACTLY these keys; arrays may be empty if nothing is found):

{{
  "drawing_type": "P&ID",
  "title": <string or null>,
  "drawing_no": <string or null>,
  "equipment": [
    {{ "tag": "...", "type": "vessel|pump|heat_exchanger|psv|tank|column|reactor|gate_valve|ball_valve|control_valve|filter|other",
       "service": <string or null> }}
  ],
  "instruments": [
    {{ "tag": "...", "function": "PT|FT|LT|FIC|TIC|LIC|...", "loop_id": "...",
       "located_on": <equipment_tag, line_no, or "panel" or null> }}
  ],
  "lines": [
    {{ "line_no": "...", "size": <e.g. \"6\\\"\">, "service": "...", "spec": "...",
       "from_tag": <tag or null>, "to_tag": <tag or null> }}
  ],
  "connections": [
    {{ "from_tag": "...", "to_tag": "...", "type": "process|signal|utility",
       "via_line": <line_no or null> }}
  ]
}}

Conventions:
- Equipment tags follow patterns like V-101 (vessel), P-101A (pump), E-101 (heat exchanger),
  PSV-101 (pressure safety valve), GV-101 (gate valve), T-201 (tank).
- Instrument tags follow ISA-5.1: function letters + loop number, e.g. PT-101, FT-201, LIC-301.
- Line numbers follow {{size}}-{{service}}-{{number}}-{{spec}}, e.g. 6"-FG-101-CS.
- A connection of type "signal" represents a dashed instrument signal line; "process" is solid piping.
- If two labels exist for the same line with different specs (e.g. -CS and -SS), report BOTH as
  separate Line entries — DO NOT silently merge them.

Drawing context: {context_hint}

Return ONLY the JSON object. Do not include explanations or code fences."""


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = _strip_fences(text)
    # Handle leading/trailing extra text
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def extract_from_image(
    image: Image.Image,
    drawing_id: str,
    context_hint: str = "Standalone P&ID page",
    use_secondary: bool = False,
    max_tokens: int = 8192,
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Run a single Vision extraction pass on the image.

    Returns (ExtractionResult, raw_meta) where raw_meta carries token usage and the
    raw model text for downstream debugging.
    """
    prompt = USER_PROMPT_TEMPLATE.format(context_hint=context_hint)
    fn = call_secondary_vision if use_secondary else call_primary_vision
    resp = fn(prompt=prompt, image=image, system=SYSTEM_PROMPT, max_tokens=max_tokens)

    parsed = _parse_json(resp.text)

    result = ExtractionResult(
        drawing_id=drawing_id,
        drawing_type=parsed.get("drawing_type", "P&ID"),
        title=parsed.get("title"),
        drawing_no=parsed.get("drawing_no"),
        equipment=tuple(from_dict_equipment(x) for x in parsed.get("equipment", [])),
        instruments=tuple(from_dict_instrument(x) for x in parsed.get("instruments", [])),
        lines=tuple(from_dict_line(x) for x in parsed.get("lines", [])),
        connections=tuple(from_dict_connection(x) for x in parsed.get("connections", [])),
    )

    raw_meta = {
        "model_id": resp.model_id,
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "stop_reason": resp.stop_reason,
        "raw_text": resp.text,
    }
    return result, raw_meta
