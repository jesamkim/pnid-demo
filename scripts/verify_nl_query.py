"""Run the NL query agent end-to-end on demo questions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.nl_query import answer
from backend.schemas import (
    ExtractionResult, from_dict_connection, from_dict_equipment,
    from_dict_instrument, from_dict_line,
)
from backend.tools.document_builder import build_docs
from backend.tools.search_index import SearchIndex

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / ".claude" / "artifacts" / "extraction"

DRAWINGS = ["01", "01b", "02", "03"]


def load_pipeline(key: str) -> ExtractionResult:
    data = json.loads((PIPELINE / f"{key}_pipeline.json").read_text())
    ex = data["extraction"]
    return ExtractionResult(
        drawing_id=key, drawing_type="P&ID",
        title=None, drawing_no=None,
        equipment=tuple(from_dict_equipment(x) for x in ex["equipment"]),
        instruments=tuple(from_dict_instrument(x) for x in ex["instruments"]),
        lines=tuple(from_dict_line(x) for x in ex["lines"]),
        connections=tuple(from_dict_connection(x) for x in ex["connections"]),
    )


def main():
    idx = SearchIndex()
    for k in DRAWINGS:
        idx.add(build_docs(load_pipeline(k)))
    print(f"Indexed {len(idx)} docs from {len(DRAWINGS)} drawings\n")

    queries = [
        "What PSV protects V-101 and what does it do?",
        "Show all pressure transmitters across drawings",
        "What does P-201A pump feed into?",
        "어느 도면에 펌프 두 대(A/B)가 평행으로 배치되어 있나요?",
        "Are there any cooling water lines, and where do they go?",
        "Which drawing has the steam preheater?",
    ]
    for q in queries:
        a = answer(q, idx)
        print(f"Q: {q}")
        print(f"A: {a.text}")
        print(f"   sources: {[h.doc.drawing_id + '|' + h.doc.tag for h in a.hits[:4]]}")
        print()


if __name__ == "__main__":
    main()
