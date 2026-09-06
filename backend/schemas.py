"""Project data contract — every agent and tool consumes/produces these.

Core principle: immutable. Equipment/Instrument/Line/Connection/Anomaly are
frozen dataclasses; ExtractionResult bundles them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


BBox = tuple[float, float, float, float]
EquipmentType = Literal[
    "vessel", "pump", "heat_exchanger", "compressor", "tank",
    "psv", "safety_valve",
    "control_valve", "gate_valve", "ball_valve",
    "filter", "column", "reactor", "vacuum_unit", "other",
]
ConnectionType = Literal["process", "signal", "utility"]


@dataclass(frozen=True)
class Equipment:
    tag: str
    type: EquipmentType
    service: Optional[str] = None
    bbox: Optional[BBox] = None
    page: int = 1
    properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Instrument:
    tag: str
    function: str  # ISA-5.1 e.g. PT, FT, LT, FIC, TIC, LIC
    loop_id: str
    located_on: Optional[str] = None
    bbox: Optional[BBox] = None
    page: int = 1


@dataclass(frozen=True)
class Line:
    line_no: str
    size: Optional[str] = None
    service: Optional[str] = None
    spec: Optional[str] = None
    from_tag: Optional[str] = None
    to_tag: Optional[str] = None
    geometry: Optional[tuple[tuple[float, float], ...]] = None
    page: int = 1


@dataclass(frozen=True)
class Connection:
    from_tag: str
    to_tag: str
    type: ConnectionType
    via_line: Optional[str] = None


@dataclass(frozen=True)
class Anomaly:
    rule: str
    severity: Literal["high", "medium", "low"]
    violated_by: str
    description: str
    suggestion: Optional[str] = None


@dataclass(frozen=True)
class ExtractionResult:
    drawing_id: str
    drawing_type: str
    title: Optional[str]
    drawing_no: Optional[str]
    equipment: tuple[Equipment, ...]
    instruments: tuple[Instrument, ...]
    lines: tuple[Line, ...]
    connections: tuple[Connection, ...]
    anomalies: tuple[Anomaly, ...] = ()
    raw_meta: dict[str, str] = field(default_factory=dict)


def from_dict_equipment(d: dict) -> Equipment:
    bbox = tuple(d["bbox"]) if d.get("bbox") else None
    return Equipment(
        tag=d["tag"], type=d["type"], service=d.get("service"),
        bbox=bbox, page=int(d.get("page", 1)),
        properties={k: str(v) for k, v in d.get("properties", {}).items()},
    )


def from_dict_instrument(d: dict) -> Instrument:
    bbox = tuple(d["bbox"]) if d.get("bbox") else None
    return Instrument(
        tag=d["tag"], function=d["function"], loop_id=d["loop_id"],
        located_on=d.get("located_on"), bbox=bbox, page=int(d.get("page", 1)),
    )


def from_dict_line(d: dict) -> Line:
    raw_geom = d.get("geometry")
    geometry = (
        tuple((float(x), float(y)) for x, y in raw_geom) if raw_geom else None
    )
    return Line(
        line_no=d["line_no"], size=d.get("size"), service=d.get("service"),
        spec=d.get("spec"), from_tag=d.get("from_tag"), to_tag=d.get("to_tag"),
        geometry=geometry,
        page=int(d.get("page", 1)),
    )


def from_dict_connection(d: dict) -> Connection:
    return Connection(
        from_tag=d["from_tag"], to_tag=d["to_tag"], type=d["type"],
        via_line=d.get("via_line"),
    )


def load_ground_truth(d: dict) -> ExtractionResult:
    return ExtractionResult(
        drawing_id=d["drawing_id"],
        drawing_type=d["drawing_type"],
        title=d.get("title"),
        drawing_no=d.get("drawing_no"),
        equipment=tuple(from_dict_equipment(x) for x in d.get("equipment", [])),
        instruments=tuple(from_dict_instrument(x) for x in d.get("instruments", [])),
        lines=tuple(from_dict_line(x) for x in d.get("lines", [])),
        connections=tuple(from_dict_connection(x) for x in d.get("connections", [])),
    )
