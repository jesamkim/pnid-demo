"""Run Evaluator on each previously extracted result.

Reads .claude/artifacts/extraction/<key>_extracted.json + the source PDF,
runs evaluator, and reports findings.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agents.evaluator import evaluate
from backend.schemas import load_ground_truth
from backend.tools.pdf_renderer import render_page

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
EXTRACT = ROOT / ".claude" / "artifacts" / "extraction"

DRAWINGS = {
    "01": "01_separator_pid.pdf",
    "01b": "01b_separator_pid_obscured.pdf",
    "02": "02_pump_hx_system.pdf",
    "03": "03_anomaly_demo.pdf",
}


def run_one(key: str):
    pdf = SAMPLES / DRAWINGS[key]
    extracted_raw = json.loads((EXTRACT / f"{key}_extracted.json").read_text())
    er = load_ground_truth(extracted_raw)  # reuses loader
    img = render_page(pdf, page=0, dpi=200)
    crit = evaluate(er, img)
    print(f"\n=== Drawing {key} ===")
    print(f"  verdict: {crit.verdict}")
    print(f"  rule_anomalies: {len(crit.rule_anomalies)}")
    for a in crit.rule_anomalies:
        print(f"    - [{a.rule}] {a.violated_by}: {a.description}")
    print(f"  llm_findings: {len(crit.llm_findings)}")
    for f in crit.llm_findings:
        print(f"    - [{f.kind}] {f.target}: {f.reason}")

    # Persist
    out = {
        "verdict": crit.verdict,
        "rule_anomalies": [asdict(a) for a in crit.rule_anomalies],
        "llm_findings": [asdict(f) for f in crit.llm_findings],
        "model": crit.raw_meta.get("model_id"),
        "input_tokens": crit.raw_meta.get("input_tokens"),
        "output_tokens": crit.raw_meta.get("output_tokens"),
    }
    (EXTRACT / f"{key}_critique.json").write_text(json.dumps(out, indent=2))
    return crit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--drawing", default="all", choices=["01", "01b", "02", "03", "all"])
    args = p.parse_args()
    keys = list(DRAWINGS.keys()) if args.drawing == "all" else [args.drawing]
    for k in keys:
        run_one(k)


if __name__ == "__main__":
    main()
