"""Run the full Self-Correction loop on a drawing.

Demonstrates the LG-blog pattern: initial extract -> critique -> error analysis
-> strategy -> re-extract -> re-critique -> ... until pass or max iterations.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.evaluator import evaluate
from backend.agents.extractor import extract_from_image
from backend.agents.self_correction import run_with_correction
from backend.tools.pdf_renderer import render_page

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
OUT = ROOT / ".claude" / "artifacts" / "extraction"

DRAWINGS = {
    "01": "01_separator_pid.pdf",
    "01b": "01b_separator_pid_obscured.pdf",
    "02": "02_pump_hx_system.pdf",
    "03": "03_anomaly_demo.pdf",
}


def run_one(key: str):
    pdf = SAMPLES / DRAWINGS[key]
    print(f"\n=== Self-Correction on Drawing {key}: {pdf.name} ===")
    img = render_page(pdf, page=0, dpi=200)

    extracted, _meta = extract_from_image(img, drawing_id=key)
    crit = evaluate(extracted, img)
    print(f"  initial verdict: {crit.verdict}")

    run = run_with_correction(img, key, extracted, crit, max_iters=3)
    print(f"  iterations_used: {run.iterations_used}")
    print(f"  final verdict:   {run.final_critique.verdict}")
    print(f"  final eq/inst/lines: {len(run.final.equipment)}/{len(run.final.instruments)}/{len(run.final.lines)}")
    print(f"\n  TIMELINE")
    for s in run.steps:
        v = f" -> verdict={s.verdict_after}" if s.verdict_after else ""
        e = f" ({s.elapsed_s}s)" if s.elapsed_s else ""
        print(f"    [{s.iteration}] {s.action}: {s.detail}{e}{v}")

    out = {
        "iterations_used": run.iterations_used,
        "final_verdict": run.final_critique.verdict,
        "final_equipment_tags": [e.tag for e in run.final.equipment],
        "final_instrument_tags": [i.tag for i in run.final.instruments],
        "steps": [asdict(s) for s in run.steps],
    }
    (OUT / f"{key}_correction_run.json").write_text(json.dumps(out, indent=2))
    return run


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--drawing", default="01b", choices=["01", "01b", "02", "03", "all"])
    args = p.parse_args()
    keys = list(DRAWINGS.keys()) if args.drawing == "all" else [args.drawing]
    for k in keys:
        run_one(k)


if __name__ == "__main__":
    main()
