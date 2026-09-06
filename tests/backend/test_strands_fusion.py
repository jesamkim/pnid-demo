"""Fusion agent tests — pure-Python rule based, no AWS calls."""
from __future__ import annotations

from backend.agents.strands_fusion import (
    FusionResult,
    _best_match,
    _enclose,
    _levenshtein,
    fuse,
)
from backend.agents.strands_ocr import TextBlock
from backend.schemas import (
    Equipment,
    ExtractionResult,
    Instrument,
    Line,
)


def _ext(eq=(), inst=(), lines=(), conn=()) -> ExtractionResult:
    return ExtractionResult(
        drawing_id="t",
        drawing_type="P&ID",
        title=None,
        drawing_no=None,
        equipment=tuple(eq),
        instruments=tuple(inst),
        lines=tuple(lines),
        connections=tuple(conn),
    )


def test_levenshtein_basic():
    assert _levenshtein("V-101", "V-101") == 0
    assert _levenshtein("V-101", "V-102") == 1
    assert _levenshtein("V-101", "V101") == 1


def test_enclose_handles_none():
    assert _enclose(None, (0, 0, 1, 1)) == (0, 0, 1, 1)
    assert _enclose((0, 0, 1, 1), None) == (0, 0, 1, 1)
    assert _enclose((0, 0, 1, 1), (2, 2, 3, 3)) == (0, 0, 3, 3)


def test_best_match_levenshtein_one():
    blocks = [
        TextBlock("V-101", 99.0, (10, 10, 100, 30)),
        TextBlock("V-102", 99.0, (200, 200, 300, 220)),
    ]
    m = _best_match("V-101", blocks)
    assert m is not None and m.text == "V-101"
    m2 = _best_match("V-101.", blocks)
    # period removed in normalisation, exact match
    assert m2 is not None and m2.text == "V-101"


def test_best_match_returns_none_when_too_far():
    blocks = [TextBlock("Z-999", 99.0, (0, 0, 1, 1))]
    assert _best_match("V-101", blocks) is None


def test_fuse_upgrades_equipment_bbox():
    eq = Equipment(tag="V-101", type="vessel", bbox=(50, 50, 200, 400))
    block = TextBlock("V-101", 98.5, (60, 60, 180, 90))
    res = fuse(_ext(eq=[eq]), [block])
    assert res.matched_equipment == 1
    assert res.extraction.equipment[0].bbox == (50, 50, 200, 400)
    # When Vision has no bbox at all, OCR's bbox is used directly.
    eq2 = Equipment(tag="V-101", type="vessel", bbox=None)
    res2 = fuse(_ext(eq=[eq2]), [block])
    assert res2.extraction.equipment[0].bbox == (60, 60, 180, 90)


def test_fuse_emits_event_per_tag():
    eq = Equipment(tag="V-101", type="vessel", bbox=None)
    block = TextBlock("V-101", 99.0, (10, 10, 100, 30))
    res = fuse(_ext(eq=[eq]), [block])
    stages = [e["stage"] for e in res.events]
    assert "fusion_match_equipment" in stages


def test_fuse_instrument_inflates_bubble():
    inst = Instrument(tag="PT-102", function="PT", loop_id="102", bbox=None)
    block = TextBlock("PT-102", 99.0, (200, 200, 230, 220))
    res = fuse(_ext(inst=[inst]), [block])
    out = res.extraction.instruments[0]
    assert out.bbox is not None
    # Inflated by 12 px on each side
    assert out.bbox[0] < 200
    assert out.bbox[2] > 230


def test_fuse_line_geometry_from_ocr_labels():
    line = Line(line_no='12"-CRD-101-CS', from_tag="A", to_tag="B")
    blocks = [
        TextBlock('12"-CRD-101-CS', 99.0, (100, 100, 200, 120)),
        TextBlock('12"-CRD-101-CS', 99.0, (400, 100, 500, 120)),
    ]
    res = fuse(_ext(lines=[line]), blocks)
    assert res.matched_lines == 1
    geom = res.extraction.lines[0].geometry
    assert geom is not None and len(geom) == 2


def test_fuse_handles_empty_ocr():
    eq = Equipment(tag="V-101", type="vessel", bbox=(0, 0, 1, 1))
    res = fuse(_ext(eq=[eq]), [])
    assert res.matched_equipment == 0
    assert res.extraction.equipment[0].bbox == (0, 0, 1, 1)
