"""Valve Scanner — focused detection of inline valves on process lines.

The main Vision extraction (even in hierarchical mode) often misses
small inline valves on DIN/ISA drawings because:
  1. Valve symbols are tiny (10-20 px) relative to equipment symbols.
  2. DIN Rule 9-11 (Phase 79) intentionally suppresses AB*-prefixed
     tokens to avoid hallucinating line design codes as valves.
  3. Zone-specialist agents focus on major equipment + instruments.

This scanner runs AFTER the main extraction and AFTER the Connection
Stitcher. It receives the full drawing image + list of known lines,
and for each zone asks Opus 4.8 to detect valve symbols that lie ON
process lines but aren't already in the equipment list.

Output is a list of Equipment items (type = gate_valve / ball_valve /
control_valve / safety_valve) with bbox, tag (if visible), and which
line they sit on.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import replace
from typing import Any

from PIL import Image
from strands import Agent

from backend.agents.strands_zone_scout import Zone, crop_zone
from backend.schemas import Equipment, ExtractionResult, from_dict_equipment
from backend.strands_models import primary_model


SYSTEM = """You are a valve symbol detector for engineering P&ID drawings.

You receive a cropped section of a P&ID. Your SOLE JOB is to find every
inline valve symbol that sits ON a process line within this crop.

Valve symbols to look for:
- Gate valve: small rectangle/bowtie shape straddling a line
- Ball valve: circle with a line through it
- Control valve: triangle-pair (bowtie) with a circle actuator on top
- Check valve: triangle pointing in flow direction
- Safety/relief valve: angled shape with spring symbol on top

For each valve found, output:
  tag: the alphanumeric label next to it (e.g. "AB014", "XV-101"), or
       "UNNAMED" if no label is visible
  type: "gate_valve" | "ball_valve" | "control_valve" | "check_valve" | "safety_valve"
  on_line: which line_no the valve sits on (if readable), else null
  bbox_norm: [left, top, right, bottom] in 0..1 relative to this crop

Return a JSON array. If no valves are found, return [].
Do NOT include items already listed in the known equipment below.

EXCLUSION: If this crop contains a title block / drawing information
table (drawing number, date, revision, company name, scale, etc.),
ignore that area completely. Title block text is NOT a valve.
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


def _parse_valves(raw: str, crop_w: int, crop_h: int, offset: tuple[int, int]) -> list[Equipment]:
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
    dx, dy = offset
    out: list[Equipment] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag", "UNNAMED")).strip()
        vtype = str(item.get("type", "gate_valve")).strip().lower()
        if vtype not in {"gate_valve", "ball_valve", "control_valve", "check_valve", "safety_valve"}:
            vtype = "gate_valve"
        bb = item.get("bbox_norm") or item.get("bbox")
        bbox = None
        if isinstance(bb, list) and len(bb) == 4:
            try:
                l, t, r, b = (float(x) for x in bb)
                bbox = (
                    round(l * crop_w + dx, 1),
                    round(t * crop_h + dy, 1),
                    round(r * crop_w + dx, 1),
                    round(b * crop_h + dy, 1),
                )
            except (TypeError, ValueError):
                pass
        on_line = item.get("on_line")
        props = {}
        if on_line:
            props["on_line"] = str(on_line)
        out.append(Equipment(
            tag=tag, type=vtype, service=None, bbox=bbox,
            page=1, properties=props,
        ))
    return out


def scan_valves(
    image: Image.Image,
    extraction: ExtractionResult,
    zones: list[Zone] | None = None,
) -> tuple[ExtractionResult, dict[str, Any]]:
    """Scan for inline valves across the drawing.

    If `zones` is provided, scans each zone crop. Otherwise scans
    the full image (less accurate for large drawings).

    Returns (updated_extraction, meta) with new valve Equipment items
    merged into the equipment tuple.
    """
    existing_tags = {e.tag for e in extraction.equipment}
    all_new: list[Equipment] = []

    if not zones:
        # Single pass on full image
        zones = [Zone(topic="full", bbox_norm=(0, 0, 1, 1))]

    for zone in zones:
        cropped, offset = crop_zone(image, zone, padding=40)
        cw, ch = cropped.size
        known_eq = [e.tag for e in extraction.equipment]
        agent = Agent(model=primary_model(), system_prompt=SYSTEM, callback_handler=None)
        user = (
            f"Zone: {zone.topic}\n"
            f"Known equipment in this drawing (do NOT re-detect these): {known_eq}\n\n"
            "Find all valve symbols in this crop."
        )
        message = [
            {"image": {"format": "png", "source": {"bytes": _image_bytes(cropped)}}},
            {"text": user},
        ]
        try:
            result = agent(message)
            raw = _agent_text(result).strip()
            valves = _parse_valves(raw, cw, ch, offset)
            for v in valves:
                if v.tag not in existing_tags:
                    all_new.append(v)
                    existing_tags.add(v.tag)
        except Exception:  # noqa: BLE001
            continue

    merged = replace(
        extraction,
        equipment=tuple(list(extraction.equipment) + all_new),
    )
    return merged, {
        "valves_found": len(all_new),
        "total_equipment": len(merged.equipment),
        "zones_scanned": len(zones),
    }
