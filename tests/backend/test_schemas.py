"""Schemas contract tests — verify ground-truth round-trip and immutability."""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backend.schemas import (
    Connection, Equipment, ExtractionResult, Instrument, Line,
    load_ground_truth,
)

GT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "ground_truth"


def test_equipment_is_frozen():
    e = Equipment(tag="V-101", type="vessel")
    with pytest.raises(FrozenInstanceError):
        e.tag = "V-102"  # type: ignore[misc]


def test_load_ground_truth_crude_main():
    raw = json.loads((GT_DIR / "01_separator_pid.json").read_text())
    r = load_ground_truth(raw)
    assert isinstance(r, ExtractionResult)
    assert r.drawing_id == "01"
    tags = {e.tag for e in r.equipment}
    assert {"V-101", "PSV-101", "P-101A", "P-101B", "E-101", "C-101", "F-101"} <= tags
    assert any(i.tag == "LT-101" for i in r.instruments)
    assert any(c.type == "signal" for c in r.connections)


def test_load_ground_truth_obscured():
    raw = json.loads((GT_DIR / "01b_separator_pid_obscured.json").read_text())
    r = load_ground_truth(raw)
    assert r.drawing_id == "01b"
    # obscured variant keeps all geometry; PSV-101 in GT but masked visually.
    assert any(e.tag == "PSV-101" for e in r.equipment)


def test_line_geometry_round_trip():
    raw = json.loads((GT_DIR / "01_separator_pid.json").read_text())
    r = load_ground_truth(raw)
    with_geom = [l for l in r.lines if l.geometry]
    assert len(with_geom) >= 10, "demo drawing should expose polyline geometry"
    sample = with_geom[0]
    assert isinstance(sample.geometry, tuple)
    assert all(isinstance(p, tuple) and len(p) == 2 for p in sample.geometry)


def test_extraction_result_tuples_are_immutable():
    e = Equipment(tag="V-1", type="vessel")
    r = ExtractionResult(
        drawing_id="t", drawing_type="P&ID", title=None, drawing_no=None,
        equipment=(e,), instruments=(), lines=(), connections=(),
    )
    assert isinstance(r.equipment, tuple)
    with pytest.raises((TypeError, AttributeError)):
        r.equipment.append(e)  # type: ignore[attr-defined]
