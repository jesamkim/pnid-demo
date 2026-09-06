"""Zone Scout — coarse pass that breaks the drawing into semantic zones.

This is the first step of the hierarchical extraction strategy:
instead of one Vision call against the whole image (or a fixed grid
of tiles), we ask Sonnet 4.6 to look at a downscaled view and report
where the real "process zones" live (the column area, the pump pack,
the heat-exchanger row, the vacuum unit, etc.).

A Zone is just a normalised bbox + a short topic. The orchestrator
then dispatches one focused Vision sub-agent per Zone, so each
sub-agent sees a smaller, more coherent slice than a fixed tile.

This module is intentionally self-contained — it does not modify the
existing tile fan-out path. Use it via the
`backend.agents.strands_extractor_hierarchical` orchestrator entry,
or directly in tests.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from typing import Any

from PIL import Image
from strands import Agent

from backend.strands_models import secondary_model


# Hard cap on the number of zones the scout can return; protects the
# downstream fan-out from cost blow-up on adversarial inputs.
MAX_ZONES = 8

# Down-sample target so the scout call stays cheap (~1.5 MB image).
SCOUT_LONG_EDGE = 1600


@dataclass(frozen=True)
class Zone:
    """One process zone identified by the scout.

    Coordinates are normalised to [0, 1] of the *original* image; the
    orchestrator maps them back to pixel coordinates before cropping.
    `topic` is a short Korean/English label describing what the zone
    is about (e.g. "KA002 Glockenbodenkolonne + side condenser").
    `priority` is "high" for safety-critical zones (PSV, vacuum unit)
    and "normal" otherwise. The orchestrator may run high-priority
    zones first.
    """
    topic: str
    bbox_norm: tuple[float, float, float, float]  # left, top, right, bottom in 0..1
    priority: str = "normal"


SYSTEM = """You are a senior P&ID reader. Your job is NOT to extract
every tag — that comes later. Your job is to look at the drawing and
report 3 to 6 process zones (rectangular regions) that group together
equipment that obviously belongs to the same sub-process.

A good zone is roughly 1/4 to 1/2 of the page in area, contains 2-6
pieces of equipment that share process function.

IMPORTANT EXCLUSIONS — do NOT create a zone for any of these:
- The title block / drawing information table (usually bottom-right,
  contains drawing number, revision, date, scale, company name)
- The legend / symbol list (if present)
- The revision history table
- Page border frames and column/row numbering
These areas contain NO process equipment and must be excluded.

For each zone, output:
  - "topic": short label (≤80 chars), in the drawing's language if
    legible (German on DIN drawings, English on ISA drawings).
    Examples: "KA002 distillation column + condensers",
              "Pump rack PA100..PA105", "BA101..BA103 storage row".
  - "bbox_norm": [left, top, right, bottom] each in 0..1 of the page.
  - "priority": "high" if the zone contains a safety device (PSV, SA,
    vacuum unit) or pressure-relief path; otherwise "normal".

Output a JSON array, exactly one entry per zone, between 3 and 6
items. Return ONLY the JSON array, no fences, no preamble."""


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


def _downscale(image: Image.Image, long_edge: int = SCOUT_LONG_EDGE) -> Image.Image:
    w, h = image.size
    m = max(w, h)
    if m <= long_edge:
        return image.convert("RGB")
    scale = long_edge / m
    return image.convert("RGB").resize(
        (max(1, int(w * scale)), max(1, int(h * scale))),
        Image.LANCZOS,
    )


def _to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _parse_zones(text: str) -> tuple[Zone, ...]:
    cleaned = _strip_fences(text)
    # Be tolerant: scout sometimes wraps in {"zones": [...]}
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to recover the first balanced array.
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            data = json.loads(cleaned[start : end + 1])
        else:
            return ()
    if isinstance(data, dict):
        data = data.get("zones") or list(data.values())[0] if data else []
    if not isinstance(data, list):
        return ()
    out: list[Zone] = []
    for entry in data[:MAX_ZONES]:
        if not isinstance(entry, dict):
            continue
        topic = str(entry.get("topic", "")).strip()[:120]
        bb = entry.get("bbox_norm") or entry.get("bbox") or []
        if not isinstance(bb, list) or len(bb) != 4:
            continue
        try:
            l, t, r, b = (float(x) for x in bb)
        except (TypeError, ValueError):
            continue
        l, t = max(0.0, min(0.99, l)), max(0.0, min(0.99, t))
        r, b = max(l + 0.05, min(1.0, r)), max(t + 0.05, min(1.0, b))
        priority = str(entry.get("priority", "normal")).lower()
        if priority not in {"high", "normal"}:
            priority = "normal"
        if not topic:
            continue
        out.append(Zone(topic=topic, bbox_norm=(l, t, r, b), priority=priority))
    return tuple(out)


def scout_zones(image: Image.Image) -> tuple[tuple[Zone, ...], dict[str, Any]]:
    """Run the scout on a full-page drawing and return identified zones.

    Returns (zones, meta). Empty `zones` means the scout did not yield
    a parseable response — callers should fall back to the existing
    tile fan-out path.
    """
    small = _downscale(image)
    agent = Agent(model=secondary_model(), system_prompt=SYSTEM, callback_handler=None)
    message = [
        {"image": {"format": "png", "source": {"bytes": _to_png_bytes(small)}}},
        {"text": (
            "Return the JSON array of zones for this P&ID. "
            f"Limit to {MAX_ZONES} zones max."
        )},
    ]
    result = agent(message)
    raw = _agent_text(result).strip()
    zones = _parse_zones(raw)
    return zones, {
        "scout_image_size": small.size,
        "raw_chars": len(raw),
        "zones": len(zones),
    }


def crop_zone(image: Image.Image, zone: Zone, padding: int = 80) -> tuple[
    Image.Image, tuple[int, int]
]:
    """Crop the original image to a zone's pixel bbox, with padding so
    instrument bubbles right at the boundary aren't clipped.

    Returns (cropped, (left_px, top_px)) so callers can shift any
    bbox the per-zone Vision agent emits back into page coordinates.
    """
    w, h = image.size
    l = max(0, int(zone.bbox_norm[0] * w) - padding)
    t = max(0, int(zone.bbox_norm[1] * h) - padding)
    r = min(w, int(zone.bbox_norm[2] * w) + padding)
    b = min(h, int(zone.bbox_norm[3] * h) + padding)
    return image.crop((l, t, r, b)), (l, t)
