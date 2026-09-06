"""End-to-end pipeline run on each demo drawing.

Records:
  - .claude/artifacts/extraction/<key>_pipeline.json  -> structured result
  - .claude/artifacts/extraction/<key>_pipeline.txt   -> human-readable timeline
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.orchestrator import ProgressEvent, run_pipeline

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
OUT = ROOT / ".claude" / "artifacts" / "extraction"

DRAWINGS = {
    "01": "01_separator_pid.pdf",
    "01b": "01b_separator_pid_obscured.pdf",
    "02": "02_pump_hx_system.pdf",
    "03": "03_anomaly_demo.pdf",
}


def _print_evt(evt: ProgressEvent) -> None:
    extra = f" {evt.extra}" if evt.extra else ""
    print(f"  [{evt.stage:>22}] {evt.detail} ({evt.elapsed_s}s){extra}")


def run_one(key: str) -> dict:
    pdf = SAMPLES / DRAWINGS[key]
    print(f"\n=== Pipeline: {key} ({pdf.name}) ===")
    result = run_pipeline(pdf, drawing_id=key, on_progress=_print_evt)
    print(f"  TOTAL: {result.total_elapsed_s}s, {len(result.anomalies)} anomalies")

    pipeline_dump = {
        "drawing_id": result.drawing_id,
        "total_elapsed_s": result.total_elapsed_s,
        "verdict": result.critique.verdict,
        "iterations_used": result.correction.iterations_used if result.correction else 0,
        "extraction": {
            "equipment": [asdict(e) for e in result.extraction.equipment],
            "instruments": [asdict(i) for i in result.extraction.instruments],
            "lines": [asdict(l) for l in result.extraction.lines],
            "connections": [asdict(c) for c in result.extraction.connections],
        },
        "anomalies": [asdict(a) for a in result.anomalies],
        "events": [asdict(e) for e in result.events],
    }
    (OUT / f"{key}_pipeline.json").write_text(json.dumps(pipeline_dump, indent=2))
    return pipeline_dump


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--drawing", default="all", choices=["01", "01b", "02", "03", "all"])
    args = p.parse_args()
    keys = list(DRAWINGS.keys()) if args.drawing == "all" else [args.drawing]
    summaries = []
    for k in keys:
        summaries.append(run_one(k))

    print("\n=== SUMMARY ===")
    for s in summaries:
        print(f"  {s['drawing_id']:>4}  verdict={s['verdict']:>17}  "
              f"iters={s['iterations_used']}  anomalies={len(s['anomalies'])}  "
              f"{s['total_elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
