"""Connection Stitcher — post-extraction agent that traces process lines.

After the main extraction has identified equipment, instruments, and
lines, this agent receives the full drawing image PLUS the current
extraction JSON and fills in missing connections (from_tag / to_tag /
via_line). It focuses on:

  1. Lines whose from_tag or to_tag is null — trace the line path on
     the drawing to identify which equipment/instrument it connects.
  2. Equipment pairs that obviously share a process line but have no
     corresponding Connection entry.
  3. Instrument signal connections — instruments mounted on equipment
     that have no signal Connection linking them.

Uses Opus 4.8 (primary_model) because accurate line-path tracing on
dense engineering drawings requires the strongest Vision grounding.
Runs once per pipeline invocation, after fusion + self-correction.
"""
from __future__ import annotations

import io
import json
from dataclasses import replace
from typing import Any

from PIL import Image
from strands import Agent

from backend.schemas import Connection, ExtractionResult
from backend.strands_models import primary_model


SYSTEM = """You are a P&ID connection analyst. You receive:
1. An image of the complete P&ID drawing.
2. A JSON extraction listing all detected equipment, instruments, and lines.

Your job is to TRACE PROCESS LINES on the drawing and identify MISSING
connections. A connection links two items (equipment, instruments) via a
line or signal path.

Rules:
- Only report connections you can visually confirm by following a line on
  the drawing. Never guess or infer from naming conventions alone.
- For each new connection, specify:
    from_tag: the tag of the origin item
    to_tag: the tag of the destination item
    type: "process" (pipe), "signal" (instrument signal), or "utility"
    via_line: the line_no if one is visible, else null
- Do NOT duplicate connections already in the input JSON.
- Focus on:
  a) Equipment → Equipment process connections (following physical pipes)
  b) Instrument → Equipment signal connections (dotted/dashed lines)
  c) Filling null from_tag/to_tag on existing lines (report as a connection)
- Return ONLY a JSON array of new Connection objects. No preamble, no fences.
  Example: [{"from_tag": "KA002", "to_tag": "WA008", "type": "process", "via_line": "LR040.22040-80-40C1200 NF 223"}]
- If you find no new connections, return an empty array: []
"""


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


def _image_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _extraction_summary(extraction: ExtractionResult) -> str:
    """Compact JSON summary for the prompt (keeps token usage manageable)."""
    data = {
        "equipment": [{"tag": e.tag, "type": e.type, "service": e.service}
                      for e in extraction.equipment],
        "instruments": [{"tag": i.tag, "function": i.function,
                         "located_on": i.located_on}
                        for i in extraction.instruments],
        "lines": [{"line_no": l.line_no, "from_tag": l.from_tag,
                   "to_tag": l.to_tag}
                  for l in extraction.lines],
        "existing_connections": [{"from_tag": c.from_tag, "to_tag": c.to_tag,
                                  "type": c.type, "via_line": c.via_line}
                                 for c in extraction.connections],
    }
    return json.dumps(data, ensure_ascii=False)


def _parse_connections(raw: str) -> list[Connection]:
    import re
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out: list[Connection] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ft = str(item.get("from_tag", "")).strip()
        tt = str(item.get("to_tag", "")).strip()
        ctype = str(item.get("type", "process")).strip().lower()
        if ctype not in {"process", "signal", "utility"}:
            ctype = "process"
        via = item.get("via_line")
        if via is not None:
            via = str(via).strip() or None
        if ft and tt:
            out.append(Connection(from_tag=ft, to_tag=tt, type=ctype, via_line=via))
    return out


def stitch_connections(
    image: Image.Image,
    extraction: ExtractionResult,
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Run the Connection Stitcher agent and merge new connections.

    Returns (updated_extraction, meta). The extraction is a new object
    with the connections tuple extended — equipment/instruments/lines
    are untouched.
    """
    agent = Agent(model=primary_model(), system_prompt=SYSTEM, callback_handler=None)
    summary = _extraction_summary(extraction)
    user = (
        f"Current extraction ({len(extraction.equipment)} eq, "
        f"{len(extraction.instruments)} inst, {len(extraction.lines)} lines, "
        f"{len(extraction.connections)} existing connections):\n"
        f"{summary}\n\n"
        "Trace lines on this drawing and return NEW connections only."
    )
    message = [
        {"image": {"format": "png", "source": {"bytes": _image_bytes(image)}}},
        {"text": user},
    ]
    result = agent(message)
    raw = _agent_text(result).strip()
    new_conns = _parse_connections(raw)

    # Dedup against existing
    existing_keys = {
        (c.from_tag, c.to_tag, c.type) for c in extraction.connections
    }
    added: list[Connection] = []
    for c in new_conns:
        key = (c.from_tag, c.to_tag, c.type)
        rev_key = (c.to_tag, c.from_tag, c.type)
        if key not in existing_keys and rev_key not in existing_keys:
            added.append(c)
            existing_keys.add(key)

    merged = replace(
        extraction,
        connections=tuple(list(extraction.connections) + added),
    )
    return merged, {
        "raw_new": len(new_conns),
        "added_after_dedup": len(added),
        "total_connections": len(merged.connections),
    }
