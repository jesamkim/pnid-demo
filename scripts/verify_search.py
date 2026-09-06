"""Build the search index from extracted/pipeline outputs and run sample queries."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.schemas import (
    Connection, Equipment, ExtractionResult, Instrument, Line,
    from_dict_connection, from_dict_equipment, from_dict_instrument, from_dict_line,
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
        r = load_pipeline(k)
        docs = build_docs(r)
        idx.add(docs)
        print(f"  indexed {k}: {len(docs)} docs")
    print(f"Total: {len(idx)} docs\n")

    queries = [
        ("Show me all PSV equipment", None),
        ("What protects V-101?", None),
        ("Find pressure transmitters", "instrument"),
        ("Pump downstream of V-101", None),
        ("Cooling water lines", "line"),
        ("Heat exchanger feeding the reactor", None),
        ("Feed pump in drawing 02", None),
    ]
    for q, kf in queries:
        print(f'Q: "{q}" (kind_filter={kf})')
        hits = idx.search(q, top_k=4, kind_filter=kf)
        for h in hits:
            print(f"   {h.score:.3f}  v={h.vector_score:.3f} k={h.keyword_score:.3f}  "
                  f"{h.doc.drawing_id}|{h.doc.kind}|{h.doc.tag}")
        print()


if __name__ == "__main__":
    main()
