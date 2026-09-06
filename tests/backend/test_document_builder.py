"""Document builder behavioral tests."""
from __future__ import annotations

import json
from pathlib import Path

from backend.schemas import load_ground_truth
from backend.tools.document_builder import build_docs

GT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "ground_truth"


def _load(name: str):
    return load_ground_truth(json.loads((GT_DIR / name).read_text()))


def test_separator_produces_one_doc_per_object():
    r = _load("01_separator_pid.json")
    docs = build_docs(r)
    assert len(docs) == len(r.equipment) + len(r.instruments) + len(r.lines)


def test_doc_text_mentions_tag_and_drawing():
    r = _load("01_separator_pid.json")
    docs = build_docs(r)
    v101 = next(d for d in docs if d.tag == "V-101")
    assert "V-101" in v101.text
    # drawing_id is the short demo key ("01"), not the source filename.
    assert r.drawing_id in v101.text


def test_psv_text_mentions_overpressure():
    r = _load("01_separator_pid.json")
    docs = build_docs(r)
    psv = next(d for d in docs if d.kind == "equipment" and d.tag.startswith("PSV"))
    assert "overpressure" in psv.text.lower()


def test_instrument_text_includes_function_meaning():
    r = _load("01_separator_pid.json")
    docs = build_docs(r)
    # New crude main drawing has PT-102 as its first PT (FT-101 is flow).
    pt = next(d for d in docs if d.tag == "PT-102")
    assert "pressure transmitter" in pt.text.lower()


def test_line_text_includes_size_service_spec():
    r = _load("01_separator_pid.json")
    docs = build_docs(r)
    line = next(d for d in docs if d.kind == "line")
    assert "Size" in line.text
    assert "Service" in line.text
