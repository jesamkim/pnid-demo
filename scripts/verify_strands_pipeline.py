"""End-to-end Strands pipeline run on each demo drawing."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.strands_orchestrator import ProgressEvent, run_pipeline

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
    print(f"\n=== Strands Pipeline: {key} ({pdf.name}) ===")
    result = run_pipeline(pdf, drawing_id=key, on_progress=_print_evt)
    print(f"  TOTAL: {result.total_elapsed_s}s, {len(result.anomalies)} anomalies")

    dump = {
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
    (OUT / f"{key}_strands_pipeline.json").write_text(json.dumps(dump, indent=2))
    return dump


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--drawing", default="all", choices=["01", "01b", "02", "03", "all"])
    args = p.parse_args()
    keys = list(DRAWINGS.keys()) if args.drawing == "all" else [args.drawing]
    summaries = [run_one(k) for k in keys]
    print("\n=== SUMMARY ===")
    for s in summaries:
        print(f"  {s['drawing_id']:>4}  verdict={s['verdict']:>17}  iters={s['iterations_used']}  "
              f"anomalies={len(s['anomalies'])}  {s['total_elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
