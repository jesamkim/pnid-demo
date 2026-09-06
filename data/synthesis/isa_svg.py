"""ISA-5.1 P&ID symbol library as SVG primitives.

Each builder returns an SVG fragment (string) plus a metadata dict suitable for
ground-truth construction. Coordinates are in SVG user units; canvas builders
position symbols and connect them with piping lines.
"""
from __future__ import annotations

from dataclasses import dataclass

STROKE = "#0d0d0d"
# v7 — sizes scaled up so labels stay legible after the PNG-rasterise
# step (canvas up to 10000 px wide for the super-complex drawing).
LINE_W = 4.0
PIPE_W = 5.0
INSTR_W = 3.0
FONT_FAMILY = 'font-family="Helvetica, Arial, sans-serif"'
TEXT_FONT = f'{FONT_FAMILY} font-size="32"'
TAG_FONT = f'{FONT_FAMILY} font-size="30" font-weight="700"'


@dataclass(frozen=True)
class Placed:
    svg: str
    tag: str
    type: str
    bbox: tuple[float, float, float, float]
    ports: dict[str, tuple[float, float]]


def vessel(cx: float, cy: float, w: float, h: float, tag: str) -> Placed:
    """Vertical pressure vessel / separator with elliptical heads."""
    x, y = cx - w / 2, cy - h / 2
    rx = w / 2
    ry = h * 0.12
    body = f"""
<g>
  <path d="M {x} {y+h*0.12}
           A {rx} {ry} 0 0 1 {x+w} {y+h*0.12}
           L {x+w} {y+h*0.88}
           A {rx} {ry} 0 0 1 {x} {y+h*0.88}
           Z"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <text x="{cx}" y="{cy+5}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="vessel",
        bbox=(x, y, x + w, y + h),
        ports={
            "top": (cx, y),
            "bottom": (cx, y + h),
            "left": (x, cy),
            "right": (x + w, cy),
        },
    )


def pump_centrifugal(cx: float, cy: float, r: float, tag: str) -> Placed:
    """Centrifugal pump: circle with triangular suction/discharge."""
    triangle = f"M {cx-r} {cy} L {cx} {cy-r} L {cx+r*1.05} {cy} Z"
    body = f"""
<g>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <path d="{triangle}" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <text x="{cx}" y="{cy+r+18}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="pump",
        bbox=(cx - r, cy - r, cx + r * 1.05, cy + r),
        ports={"suction": (cx - r, cy), "discharge": (cx + r * 1.05, cy)},
    )


def heat_exchanger(cx: float, cy: float, w: float, h: float, tag: str) -> Placed:
    """Shell-and-tube heat exchanger."""
    x, y = cx - w / 2, cy - h / 2
    body = f"""
<g>
  <rect x="{x}" y="{y}" width="{w}" height="{h}"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" rx="6" />
  <line x1="{x+w*0.12}" y1="{y}" x2="{x+w*0.12}" y2="{y+h}" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <line x1="{x+w*0.88}" y1="{y}" x2="{x+w*0.88}" y2="{y+h}" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <text x="{cx}" y="{cy+5}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="heat_exchanger",
        bbox=(x, y, x + w, y + h),
        ports={
            "tube_in": (x, cy - h * 0.2),
            "tube_out": (x + w, cy - h * 0.2),
            "shell_in": (x, cy + h * 0.2),
            "shell_out": (x + w, cy + h * 0.2),
        },
    )


def gate_valve(cx: float, cy: float, size: float, tag: str, vertical: bool = False) -> Placed:
    """Two opposed triangles ⊳⊲ representing a gate valve."""
    s = size
    if vertical:
        body = f"""
<g>
  <path d="M {cx-s} {cy-s} L {cx+s} {cy-s} L {cx} {cy} Z" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <path d="M {cx-s} {cy+s} L {cx+s} {cy+s} L {cx} {cy} Z" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <text x="{cx+s+8}" y="{cy+5}" {TAG_FONT}>{tag}</text>
</g>"""
        ports = {"in": (cx, cy - s), "out": (cx, cy + s)}
        bbox = (cx - s, cy - s, cx + s + 60, cy + s)
    else:
        body = f"""
<g>
  <path d="M {cx-s} {cy-s} L {cx-s} {cy+s} L {cx} {cy} Z" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <path d="M {cx+s} {cy-s} L {cx+s} {cy+s} L {cx} {cy} Z" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <text x="{cx}" y="{cy-s-6}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
        ports = {"in": (cx - s, cy), "out": (cx + s, cy)}
        bbox = (cx - s, cy - s - 20, cx + s, cy + s)
    return Placed(svg=body, tag=tag, type="gate_valve", bbox=bbox, ports=ports)


def psv(cx: float, cy: float, size: float, tag: str) -> Placed:
    """Pressure-Safety-Valve: triangle pointing up with disc on top."""
    s = size
    body = f"""
<g>
  <path d="M {cx-s*0.6} {cy} L {cx+s*0.6} {cy} L {cx} {cy-s} Z"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <line x1="{cx}" y1="{cy-s}" x2="{cx}" y2="{cy-s*1.6}" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <line x1="{cx-s*0.4}" y1="{cy-s*1.6}" x2="{cx+s*0.4}" y2="{cy-s*1.6}" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <text x="{cx+s*0.7}" y="{cy-s*0.3}" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="psv",
        bbox=(cx - s * 0.6, cy - s * 1.6, cx + s * 0.6 + 60, cy),
        ports={"in": (cx, cy), "out": (cx, cy - s * 1.6)},
    )


def instrument(cx: float, cy: float, r: float, function: str, loop: str) -> Placed:
    """ISA-5.1 instrument bubble: circle with horizontal line + tag."""
    tag = f"{function}-{loop}"
    body = f"""
<g>
  <circle cx="{cx}" cy="{cy}" r="{r}"
          fill="white" stroke="{STROKE}" stroke-width="{INSTR_W}" />
  <line x1="{cx-r}" y1="{cy}" x2="{cx+r}" y2="{cy}" stroke="{STROKE}" stroke-width="{INSTR_W}" />
  <text x="{cx}" y="{cy-3}" text-anchor="middle" {TAG_FONT}>{function}</text>
  <text x="{cx}" y="{cy+r*0.55}" text-anchor="middle" {TAG_FONT}>{loop}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="instrument",
        bbox=(cx - r, cy - r, cx + r, cy + r),
        ports={"signal": (cx, cy + r), "process": (cx, cy - r)},
    )


def column(cx: float, cy: float, w: float, h: float, tag: str, n_trays: int = 8) -> Placed:
    """Distillation column: tall vessel with tray lines and elliptical heads."""
    x, y = cx - w / 2, cy - h / 2
    rx = w / 2
    ry = h * 0.04
    trays = ""
    inner_top = y + h * 0.12
    inner_bot = y + h * 0.88
    inner_h = inner_bot - inner_top
    for i in range(1, n_trays + 1):
        ty = inner_top + inner_h * (i / (n_trays + 1))
        trays += f'<line x1="{x+w*0.10}" y1="{ty}" x2="{x+w*0.90}" y2="{ty}" stroke="{STROKE}" stroke-width="1" />\n  '
    body = f"""
<g>
  <path d="M {x} {y+h*0.04}
           A {rx} {ry} 0 0 1 {x+w} {y+h*0.04}
           L {x+w} {y+h*0.96}
           A {rx} {ry} 0 0 1 {x} {y+h*0.96}
           Z"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  {trays}
  <text x="{cx}" y="{cy+5}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="column",
        bbox=(x, y, x + w, y + h),
        ports={
            "top": (cx, y),
            "bottom": (cx, y + h),
            "feed": (x, cy),
            "reflux": (x + w, y + h * 0.18),
            "reboiler_in": (x + w, y + h * 0.85),
            "reboiler_out": (x, y + h * 0.92),
            "side_draw": (x + w, cy),
        },
    )


def fired_heater(cx: float, cy: float, w: float, h: float, tag: str) -> Placed:
    """Fired heater (process furnace): rectangle with flame baffles + stack."""
    x, y = cx - w / 2, cy - h / 2
    flame = ""
    for i in range(1, 4):
        fx = x + w * (0.20 + 0.20 * i)
        flame += f'<path d="M {fx} {y+h*0.85} Q {fx-8} {y+h*0.55} {fx} {y+h*0.40} Q {fx+8} {y+h*0.55} {fx} {y+h*0.85} Z" fill="#ffe0b3" stroke="{STROKE}" stroke-width="1" />\n  '
    body = f"""
<g>
  <rect x="{x}" y="{y+h*0.10}" width="{w}" height="{h*0.90}"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <rect x="{x+w*0.42}" y="{y}" width="{w*0.16}" height="{h*0.10}"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  {flame}
  <text x="{cx}" y="{y+h*0.25}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="furnace",
        bbox=(x, y, x + w, y + h),
        ports={
            "process_in": (x, cy + h * 0.20),
            "process_out": (x + w, cy - h * 0.10),
            "fuel_in": (x, cy + h * 0.40),
            "stack": (cx, y),
        },
    )


def air_cooler(cx: float, cy: float, w: float, h: float, tag: str) -> Placed:
    """Air-cooled heat exchanger: rectangle with two fan circles inside."""
    x, y = cx - w / 2, cy - h / 2
    fan_r = h * 0.30
    f1x, f2x = x + w * 0.30, x + w * 0.70
    body = f"""
<g>
  <rect x="{x}" y="{y}" width="{w}" height="{h}"
        fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <circle cx="{f1x}" cy="{cy}" r="{fan_r}" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <circle cx="{f2x}" cy="{cy}" r="{fan_r}" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <line x1="{f1x-fan_r*0.7}" y1="{cy-fan_r*0.7}" x2="{f1x+fan_r*0.7}" y2="{cy+fan_r*0.7}" stroke="{STROKE}" stroke-width="1.4" />
  <line x1="{f1x+fan_r*0.7}" y1="{cy-fan_r*0.7}" x2="{f1x-fan_r*0.7}" y2="{cy+fan_r*0.7}" stroke="{STROKE}" stroke-width="1.4" />
  <line x1="{f2x-fan_r*0.7}" y1="{cy-fan_r*0.7}" x2="{f2x+fan_r*0.7}" y2="{cy+fan_r*0.7}" stroke="{STROKE}" stroke-width="1.4" />
  <line x1="{f2x+fan_r*0.7}" y1="{cy-fan_r*0.7}" x2="{f2x-fan_r*0.7}" y2="{cy+fan_r*0.7}" stroke="{STROKE}" stroke-width="1.4" />
  <text x="{cx}" y="{y+h+18}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="air_cooler",
        bbox=(x, y, x + w, y + h + 20),
        ports={"in": (x, cy), "out": (x + w, cy)},
    )


def check_valve(cx: float, cy: float, size: float, tag: str) -> Placed:
    """Check valve: gate-valve symbol with arrow inside."""
    s = size
    body = f"""
<g>
  <path d="M {cx-s} {cy-s} L {cx-s} {cy+s} L {cx} {cy} Z" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <path d="M {cx+s} {cy-s} L {cx+s} {cy+s} L {cx} {cy} Z" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <circle cx="{cx}" cy="{cy}" r="{s*0.35}" fill="{STROKE}" />
  <text x="{cx}" y="{cy-s-6}" text-anchor="middle" {TAG_FONT}>{tag}</text>
</g>"""
    return Placed(
        svg=body,
        tag=tag,
        type="check_valve",
        bbox=(cx - s, cy - s - 20, cx + s, cy + s),
        ports={"in": (cx - s, cy), "out": (cx + s, cy)},
    )


def pipe(p1: tuple[float, float], p2: tuple[float, float], elbow: str = "h") -> str:
    """Orthogonal pipe routing. elbow='h' goes horizontal first, 'v' vertical first."""
    x1, y1 = p1
    x2, y2 = p2
    if elbow == "h":
        d = f"M {x1} {y1} L {x2} {y1} L {x2} {y2}"
    else:
        d = f"M {x1} {y1} L {x1} {y2} L {x2} {y2}"
    return f'<path d="{d}" fill="none" stroke="{STROKE}" stroke-width="{PIPE_W}" />'


def signal(p1: tuple[float, float], p2: tuple[float, float], elbow: str = "h") -> str:
    """Dashed signal line (instrument)."""
    x1, y1 = p1
    x2, y2 = p2
    if elbow == "h":
        d = f"M {x1} {y1} L {x2} {y1} L {x2} {y2}"
    else:
        d = f"M {x1} {y1} L {x1} {y2} L {x2} {y2}"
    return f'<path d="{d}" fill="none" stroke="{STROKE}" stroke-width="{INSTR_W}" stroke-dasharray="4 3" />'


def line_label(x: float, y: float, line_no: str) -> str:
    return f'<text x="{x}" y="{y}" {TEXT_FONT} fill="#444">{line_no}</text>'


def title_block(x: float, y: float, w: float, h: float, project: str, drawing_no: str, title: str, rev: str = "0") -> str:
    return f"""
<g>
  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" stroke="{STROKE}" stroke-width="{LINE_W}" />
  <line x1="{x}" y1="{y+h*0.33}" x2="{x+w}" y2="{y+h*0.33}" stroke="{STROKE}" stroke-width="1" />
  <line x1="{x}" y1="{y+h*0.66}" x2="{x+w}" y2="{y+h*0.66}" stroke="{STROKE}" stroke-width="1" />
  <text x="{x+10}" y="{y+25}" {TEXT_FONT} font-weight="700">PROJECT: {project}</text>
  <text x="{x+10}" y="{y+h*0.33+25}" {TEXT_FONT}>TITLE: {title}</text>
  <text x="{x+10}" y="{y+h*0.66+25}" {TEXT_FONT}>DWG NO: {drawing_no}    REV: {rev}</text>
</g>"""


def svg_doc(width: int, height: int, body: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
<rect width="{width}" height="{height}" fill="white" />
{body}
</svg>"""
