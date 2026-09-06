"""Process-local state: search index + cached pipeline results.

Singleton-style. Re-built lazily from artifacts when the API process starts
so the demo is functional even on cold cloud start.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Optional

from backend.agents.orchestrator import PipelineResult
from backend.schemas import (
    ExtractionResult, from_dict_connection, from_dict_equipment,
    from_dict_instrument, from_dict_line,
)
from backend.tools.document_builder import build_docs
from backend.tools.search_index import SearchIndex


ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS = ROOT / ".claude" / "artifacts" / "extraction"
SAMPLES = ROOT / "data" / "samples"
SAMPLES_REAL = ROOT / "data" / "samples_real"
GROUND_TRUTH = ROOT / "data" / "ground_truth"

DRAWING_KEYS = ["00", "01", "01b", "02_din_kaelte"]
HERO_KEYS = {"00", "01", "01b", "02_din_kaelte"}
PRESTAGED_KEYS: set[str] = set()      # collapsed in v7 — 00 carries the demo
REAL_KEYS: set[str] = set()           # real PDF retired — DIN now synthetic
DRAWING_PDFS = {
    "00":            "00_complex_refinery.pdf",
    "01":            "01_separator_pid.pdf",
    "01b":           "01b_separator_pid_obscured.pdf",
    # Synthetic DIN EN 10628 drawing (refrigeration + vacuum station) —
    # German tags/services, drawing-00 complexity, full ground truth so
    # every object is recognised. Exercises the convention auto-detect.
    "02_din_kaelte": "02_din_kaelte.pdf",
}
DRAWING_GROUND_TRUTH = {
    "00":            "00_complex_refinery.json",
    "01":            "01_separator_pid.json",
    "01b":           "01b_separator_pid_obscured.json",
    "02_din_kaelte": "02_din_kaelte.json",
}
DRAWING_TITLES = {
    "00":            "Crude / Vacuum / Hydrotreater Integrated Train (50+ eq, 60+ inst)",
    "01":            "Crude Charge and Feed Section",
    "01b":           "Crude Charge and Feed Section (occluded — self-correction demo)",
    "02_din_kaelte": "Kälteerzeugung und Vakuumstation — DIN EN 10628 (38 eq, 53 inst)",
}
DRAWING_SOURCES = {
    "02_din_kaelte": (
        "Synthetic DIN EN 10628 / DIN 19227 drawing — German tag scheme "
        "(KA/BA/WA/PA, LR line numbers); exercises convention auto-detect"
    ),
}


def has_ground_truth(key: str) -> bool:
    return key in DRAWING_GROUND_TRUTH


def is_real_sample(key: str) -> bool:
    return key in REAL_KEYS


@dataclass
class CachedRun:
    drawing_id: str
    pipeline_dump: dict


class AppState:
    def __init__(self) -> None:
        self._lock = Lock()
        self.index = SearchIndex()
        self.cached_runs: dict[str, CachedRun] = {}
        self._index_built = False

    def _pipeline_path(self, key: str) -> Optional[Path]:
        """Prefer the Strands pipeline cache; fall back to the legacy one."""
        strands = ARTIFACTS / f"{key}_strands_pipeline.json"
        if strands.exists():
            return strands
        legacy = ARTIFACTS / f"{key}_pipeline.json"
        if legacy.exists():
            return legacy
        return None

    def _load_extraction(self, key: str) -> Optional[ExtractionResult]:
        path = self._pipeline_path(key)
        if path is None:
            return None
        data = json.loads(path.read_text())
        ex = data["extraction"]
        return ExtractionResult(
            drawing_id=key, drawing_type="P&ID", title=None, drawing_no=None,
            equipment=tuple(from_dict_equipment(x) for x in ex["equipment"]),
            instruments=tuple(from_dict_instrument(x) for x in ex["instruments"]),
            lines=tuple(from_dict_line(x) for x in ex["lines"]),
            connections=tuple(from_dict_connection(x) for x in ex["connections"]),
        )

    def ensure_index(self) -> None:
        with self._lock:
            if self._index_built:
                return
            for k in DRAWING_KEYS:
                path = self._pipeline_path(k)
                if path is None:
                    continue
                r = self._load_extraction(k)
                if r is None:
                    continue
                self.index.add(build_docs(r))
                self.cached_runs[k] = CachedRun(
                    drawing_id=k, pipeline_dump=json.loads(path.read_text())
                )
            self._index_built = True


_STATE: Optional[AppState] = None


def state() -> AppState:
    global _STATE
    if _STATE is None:
        _STATE = AppState()
    return _STATE
