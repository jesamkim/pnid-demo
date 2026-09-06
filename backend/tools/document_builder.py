"""Build searchable documents from an ExtractionResult.

Each Equipment/Instrument/Line becomes one document. The document carries:
  - id: unique key like "drawing|equipment|V-101"
  - drawing_id, kind, tag/line_no
  - text: a natural-language description used for embedding
  - structured fields for filtering (type, function, service)

The text builder is the source of all retrieval quality — it should mention
synonyms, common engineering terms, and connections to make zero-shot
queries (e.g. "what protects V-101?") match.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.schemas import (
    Connection, Equipment, ExtractionResult, Instrument, Line,
)


@dataclass(frozen=True)
class SearchDoc:
    id: str
    drawing_id: str
    kind: str  # "equipment" | "instrument" | "line"
    tag: str
    text: str
    fields: dict = field(default_factory=dict)


def _equipment_text(e: Equipment, drawing_id: str, conns: tuple[Connection, ...]) -> str:
    upstream = [c.from_tag for c in conns if c.to_tag == e.tag and c.from_tag]
    downstream = [c.to_tag for c in conns if c.from_tag == e.tag and c.to_tag]
    parts = [
        f"Equipment {e.tag} of type {e.type}.",
        f"Service: {e.service}." if e.service else "",
        f"Drawing: {drawing_id}.",
        f"Upstream: {', '.join(upstream)}." if upstream else "",
        f"Downstream: {', '.join(downstream)}." if downstream else "",
    ]
    if e.type in {"psv", "safety_valve"}:
        parts.append("Pressure safety valve providing overpressure protection.")
    if e.type == "vessel":
        parts.append("Pressure vessel.")
    if e.type == "pump":
        parts.append("Centrifugal pump moving fluid downstream.")
    if e.type == "heat_exchanger":
        parts.append("Heat exchanger transferring thermal energy between streams.")
    if e.type == "vacuum_unit":
        parts.append("Vacuum unit / Vakuumstation maintaining sub-atmospheric pressure.")
    if e.type == "column":
        parts.append("Distillation / fractionation column.")
    if e.type == "reactor":
        parts.append("Process reactor.")
    if e.type == "filter":
        parts.append("Filter for solids removal.")
    return " ".join(p for p in parts if p)


def _instrument_text(i: Instrument, drawing_id: str, conns: tuple[Connection, ...]) -> str:
    targets = [c.to_tag for c in conns if c.type == "signal" and c.from_tag == i.tag and c.to_tag]
    sources = [c.from_tag for c in conns if c.type == "signal" and c.to_tag == i.tag and c.from_tag]
    parts = [
        f"Instrument {i.tag} with ISA function {i.function}.",
        f"Loop: {i.loop_id}.",
        f"Located on: {i.located_on}." if i.located_on else "",
        f"Drawing: {drawing_id}.",
        f"Signal target: {', '.join(targets)}." if targets else "",
        f"Signal source: {', '.join(sources)}." if sources else "",
    ]
    role = {
        "PT": "pressure transmitter",
        "FT": "flow transmitter",
        "LT": "level transmitter",
        "TT": "temperature transmitter",
        "LIT": "level indicating transmitter",
        "FIC": "flow indicator controller",
        "TIC": "temperature indicator controller",
        "LIC": "level indicator controller",
        "PIC": "pressure indicator controller",
    }.get(i.function)
    if role:
        parts.append(f"Function meaning: {role}.")
    return " ".join(p for p in parts if p)


def _line_text(l: Line, drawing_id: str) -> str:
    parts = [
        f"Process line {l.line_no}.",
        f"Size: {l.size}." if l.size else "",
        f"Service: {l.service}." if l.service else "",
        f"Spec: {l.spec}." if l.spec else "",
        f"From {l.from_tag} to {l.to_tag}." if (l.from_tag and l.to_tag) else "",
        f"Drawing: {drawing_id}.",
    ]
    return " ".join(p for p in parts if p)


def build_docs(r: ExtractionResult) -> tuple[SearchDoc, ...]:
    out: list[SearchDoc] = []
    for e in r.equipment:
        out.append(SearchDoc(
            id=f"{r.drawing_id}|equipment|{e.tag}",
            drawing_id=r.drawing_id, kind="equipment", tag=e.tag,
            text=_equipment_text(e, r.drawing_id, r.connections),
            fields={"type": e.type, "service": e.service or ""},
        ))
    for i in r.instruments:
        out.append(SearchDoc(
            id=f"{r.drawing_id}|instrument|{i.tag}",
            drawing_id=r.drawing_id, kind="instrument", tag=i.tag,
            text=_instrument_text(i, r.drawing_id, r.connections),
            fields={"function": i.function, "loop_id": i.loop_id,
                    "located_on": i.located_on or ""},
        ))
    for l in r.lines:
        out.append(SearchDoc(
            id=f"{r.drawing_id}|line|{l.line_no}",
            drawing_id=r.drawing_id, kind="line", tag=l.line_no,
            text=_line_text(l, r.drawing_id),
            fields={"size": l.size or "", "service": l.service or "",
                    "spec": l.spec or ""},
        ))
    return tuple(out)
