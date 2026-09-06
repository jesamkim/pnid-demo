"""Benchmark single-call extraction vs full Self-Correction pipeline.

Compares on the four demo drawings:
  - Mode A: single-call Vision extraction only (Slice 1.4 baseline)
  - Mode B: full pipeline (extract + evaluate + self-correct)

Reports for each drawing:
  - elapsed time, tokens, equipment/instrument/line counts
  - count of confirmed anomalies (Mode B only)
  - whether the result matches ground truth (counts)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.extractor import extract_from_image
from backend.agents.orchestrator import run_pipeline
from backend.tools.pdf_renderer import render_page

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
GT = ROOT / "data" / "ground_truth"
OUT = ROOT / ".claude" / "artifacts" / "benchmark"
OUT.mkdir(parents=True, exist_ok=True)

DRAWINGS = {
    "01": ("01_separator_pid.pdf", "01_separator_pid.json"),
    "01b": ("01b_separator_pid_obscured.pdf", "01b_separator_pid_obscured.json"),
    "02": ("02_pump_hx_system.pdf", "02_pump_hx_system.json"),
    "03": ("03_anomaly_demo.pdf", "03_anomaly_demo.json"),
}


def gt_counts(name: str) -> dict:
    d = json.loads((GT / name).read_text())
    return {
        "equipment": len(d.get("equipment", [])),
        "instruments": len(d.get("instruments", [])),
        "lines": len(d.get("lines", [])),
        "expected_anomalies": len(d.get("expected_anomalies", [])),
    }


def bench_drawing(key: str) -> dict:
    pdf_name, gt_name = DRAWINGS[key]
    pdf = SAMPLES / pdf_name
    gt = gt_counts(gt_name)

    # Mode A: single call
    img = render_page(pdf, page=0, dpi=200)
    t0 = time.time()
    a, meta = extract_from_image(img, drawing_id=key)
    a_elapsed = time.time() - t0

    # Mode B: full pipeline
    t0 = time.time()
    pr = run_pipeline(pdf, drawing_id=key)
    b_elapsed = time.time() - t0

    iters = pr.correction.iterations_used if pr.correction else 0

    return {
        "drawing": key,
        "ground_truth": gt,
        "mode_a_single_call": {
            "elapsed_s": round(a_elapsed, 1),
            "input_tokens": meta["input_tokens"],
            "output_tokens": meta["output_tokens"],
            "equipment": len(a.equipment),
            "instruments": len(a.instruments),
            "lines": len(a.lines),
        },
        "mode_b_pipeline": {
            "elapsed_s": round(b_elapsed, 1),
            "iterations": iters,
            "verdict": pr.critique.verdict,
            "equipment": len(pr.extraction.equipment),
            "instruments": len(pr.extraction.instruments),
            "lines": len(pr.extraction.lines),
            "anomalies_reported": len(pr.anomalies),
        },
    }


def render_table(results: list[dict]) -> str:
    rows = []
    rows.append("| Drawing | GT (Eq/Ins/Ln) | Single-Call | Pipeline (iters) | Pipeline anomalies |")
    rows.append("|---|---|---|---|---|")
    for r in results:
        gt = r["ground_truth"]
        a = r["mode_a_single_call"]
        b = r["mode_b_pipeline"]
        rows.append(
            f"| {r['drawing']} | {gt['equipment']}/{gt['instruments']}/{gt['lines']} | "
            f"{a['equipment']}/{a['instruments']}/{a['lines']} ({a['elapsed_s']}s) | "
            f"{b['equipment']}/{b['instruments']}/{b['lines']} (iters={b['iterations']}, {b['elapsed_s']}s) | "
            f"{b['anomalies_reported']} (expected {gt['expected_anomalies']}) |"
        )
    return "\n".join(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--drawing", default="all", choices=["01", "01b", "02", "03", "all"])
    args = p.parse_args()
    keys = list(DRAWINGS.keys()) if args.drawing == "all" else [args.drawing]
    results = [bench_drawing(k) for k in keys]
    print("\n=== BENCHMARK RESULTS ===\n")
    print(render_table(results))

    (OUT / "benchmark_results.json").write_text(json.dumps(results, indent=2))
    (OUT / "benchmark_results.md").write_text("# Benchmark Results\n\n" + render_table(results) + "\n")
    print(f"\nSaved to {OUT}/benchmark_results.{{json,md}}")


if __name__ == "__main__":
    main()
