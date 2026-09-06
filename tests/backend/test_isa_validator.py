"""ISA validator behavioral tests.

The Crude Unit demo drawings (01 / 01b) are clean — both end up with
no rule violations after self-correction. To verify the validator's
detection logic for the three rules (R1 PSV protection, R2 orphan
instrument, R3 pipe spec inconsistency) we build small in-test
fixtures that intentionally trip each rule. This keeps the test layer
independent of the demo's hero drawings.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.isa_validator import validate
from backend.schemas import load_ground_truth

GT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "ground_truth"


def _result(name: str):
    return load_ground_truth(json.loads((GT_DIR / name).read_text()))


def _from_dict(payload: dict):
    return load_ground_truth(payload)


# ---------- demo-drawing checks --------------------------------------------

def test_v101_passes_psv_rule_via_explicit_connection():
    """V-101 is explicitly linked to PSV-101 via a Connection, so the
    R1 rule should not flag it even when other vessels in the drawing
    do trip the rule."""
    r = _result("01_separator_pid.json")
    anomalies = validate(r)
    psv_anomalies = [a for a in anomalies if a.rule == "vessel_without_psv_protection"]
    flagged = {a.violated_by for a in psv_anomalies}
    assert "V-101" not in flagged


def test_main_drawing_flags_unprotected_vessels():
    """V-102 (bottoms surge drum) and C-101 (column) are intentionally
    left without explicit PSV connections in the demo drawing so the
    UI's ISA-5.1 panel always has visible content."""
    r = _result("01_separator_pid.json")
    anomalies = validate(r)
    psv_anomalies = [a for a in anomalies if a.rule == "vessel_without_psv_protection"]
    flagged = {a.violated_by for a in psv_anomalies}
    assert {"V-102", "C-101"} <= flagged


def test_atmospheric_tank_does_not_require_psv():
    """T-101 is a `tank`, not a `vessel` — atmospheric tanks vent through
    an open vent and should not be flagged by the PSV rule."""
    r = _result("01_separator_pid.json")
    flagged = {a.violated_by for a in validate(r)
                if a.rule == "vessel_without_psv_protection"}
    assert "T-101" not in flagged


def test_validator_returns_tuple():
    r = _result("01_separator_pid.json")
    out = validate(r)
    assert isinstance(out, tuple)


# ---------- rule-by-rule fixtures ------------------------------------------

def test_rule_vessel_without_psv():
    """R1: a pressure vessel with no PSV connection should be flagged."""
    payload = {
        "drawing_id": "T-R1",
        "drawing_type": "P&ID",
        "title": "vessel_without_psv fixture",
        "drawing_no": "TEST-R1",
        "canvas_size": {"width": 100, "height": 100},
        "equipment": [
            {"tag": "V-901", "type": "vessel", "service": "Demo unprotected vessel",
             "bbox": [10, 10, 50, 90]},
        ],
        "instruments": [],
        "lines": [
            {"line_no": '6"-FG-901-CS', "size": '6"', "service": "FG", "spec": "CS",
             "from_tag": "INLET", "to_tag": "V-901"},
        ],
        "connections": [
            {"from_tag": "INLET", "to_tag": "V-901", "type": "pipe",
             "via_line": '6"-FG-901-CS'},
        ],
        "expected_anomalies": [],
    }
    r = _from_dict(payload)
    rules = {a.rule for a in validate(r)}
    assert "vessel_without_psv_protection" in rules


def test_rule_orphan_instrument():
    """R2: an instrument with no signal connection should be flagged."""
    payload = {
        "drawing_id": "T-R2",
        "drawing_type": "P&ID",
        "title": "orphan instrument fixture",
        "drawing_no": "TEST-R2",
        "canvas_size": {"width": 100, "height": 100},
        "equipment": [
            {"tag": "V-901", "type": "vessel", "bbox": [10, 10, 50, 90]},
            {"tag": "PSV-901", "type": "psv", "bbox": [40, 0, 60, 10]},
        ],
        "instruments": [
            {"tag": "PT-902", "function": "PT", "loop_id": "902",
             "located_on": None, "bbox": [70, 70, 90, 90]},
        ],
        "lines": [
            {"line_no": '4"-PSV-901-CS', "size": '4"', "service": "PSV", "spec": "CS",
             "from_tag": "V-901", "to_tag": "PSV-901"},
        ],
        "connections": [
            {"from_tag": "V-901", "to_tag": "PSV-901", "type": "pipe",
             "via_line": '4"-PSV-901-CS'},
        ],
        "expected_anomalies": [],
    }
    r = _from_dict(payload)
    anomalies = validate(r)
    orphans = [a for a in anomalies if a.rule == "orphan_instrument"]
    assert orphans, f"expected orphan_instrument but got {anomalies}"
    assert any("PT-902" in a.violated_by for a in orphans)


def test_rule_pipe_spec_inconsistency():
    """R3: same line carried with two different specs is a violation."""
    payload = {
        "drawing_id": "T-R3",
        "drawing_type": "P&ID",
        "title": "spec inconsistency fixture",
        "drawing_no": "TEST-R3",
        "canvas_size": {"width": 100, "height": 100},
        "equipment": [
            {"tag": "V-901", "type": "vessel", "bbox": [10, 10, 50, 90]},
            {"tag": "PSV-901", "type": "psv", "bbox": [40, 0, 60, 10]},
            {"tag": "V-902", "type": "vessel", "bbox": [60, 10, 90, 90]},
            {"tag": "PSV-902", "type": "psv", "bbox": [80, 0, 95, 10]},
        ],
        "instruments": [],
        "lines": [
            {"line_no": '8"-CRD-903-CS', "size": '8"', "service": "CRD", "spec": "CS",
             "from_tag": "V-901", "to_tag": "V-902"},
            {"line_no": '8"-CRD-903-A106', "size": '8"', "service": "CRD",
             "spec": "A106", "from_tag": "V-901", "to_tag": "V-902"},
        ],
        "connections": [
            {"from_tag": "V-901", "to_tag": "V-902", "type": "pipe",
             "via_line": '8"-CRD-903-CS'},
            {"from_tag": "V-901", "to_tag": "PSV-901", "type": "pipe",
             "via_line": '4"-PSV-901-CS'},
            {"from_tag": "V-902", "to_tag": "PSV-902", "type": "pipe",
             "via_line": '4"-PSV-902-CS'},
        ],
        "expected_anomalies": [],
    }
    r = _from_dict(payload)
    rules = {a.rule for a in validate(r)}
    assert "pipe_spec_inconsistency" in rules
