"""Synthesize Drawing 1b: Three-Phase Separator with PSV area obscured.

Used for the Self-Correction demo: agent's first pass should miss PSV-101
because a black redaction box covers the top-left vessel area. Re-extract
loop should recover it after the Evaluator flags "vessel without overpressure
protection" via ISA rule.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data.synthesis import isa_svg as S
from data.synthesis.separator_pid import build as build_baseline

OUT_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLES = OUT_DIR / "data" / "samples"
GT = OUT_DIR / "data" / "ground_truth"


def main() -> int:
    svg, gt = build_baseline()
    # PSV-101 lives at cx=900,cy=290; covering its bubble + label + branch line
    redaction = '<rect x="820" y="190" width="200" height="170" fill="#1a1a1a" />'
    svg = svg.replace("</svg>", redaction + "\n</svg>")

    gt_obs = dict(gt)
    gt_obs["drawing_id"] = "01b_separator_pid_obscured"
    gt_obs["title"] = gt["title"] + " (PSV redacted — self-correction demo)"
    gt_obs["expected_anomalies"] = [
        {"rule": "vessel_without_psv_protection",
         "violated_by": "V-101 (PSV-101 hidden by redaction)",
         "expected_resolution": "self-correction loop re-extracts top-left region"}
    ]

    svg_path = SAMPLES / "01b_separator_pid_obscured.svg"
    pdf_path = SAMPLES / "01b_separator_pid_obscured.pdf"
    gt_path = GT / "01b_separator_pid_obscured.json"

    svg_path.write_text(svg)
    gt_path.write_text(json.dumps(gt_obs, indent=2))

    import cairosvg
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(pdf_path),
                     output_width=2700, output_height=1600)
    print(f"WROTE: {svg_path}, {pdf_path}, {gt_path}")
    print(f"Redaction: covers (500,120)-(780,300) which contains PSV-101")
    return 0


if __name__ == "__main__":
    sys.exit(main())
