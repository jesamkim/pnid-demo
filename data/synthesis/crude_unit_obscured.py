"""Crude unit feed P&ID with the V-101 / PSV-101 region masked.

Triggers the self-correction demo: the first vision pass mistakes the
masked PSV-101 for a missing safety device, the ISA Critic flags the
"vessel without PSV protection" rule, and the loop re-extracts focused
on the upper-left occluded patch.

Geometry mirrors `crude_unit_main.py` so the ground-truth keys overlap
1:1; the only diff is the rendered SVG has a black overlay rectangle
above the V-101 + PSV-101 region.
"""
from __future__ import annotations

import json
from pathlib import Path

import cairosvg

from data.synthesis import crude_unit_main as main_mod
from data.synthesis import isa_svg as I

ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLES = ROOT / "data" / "samples"
GT = ROOT / "data" / "ground_truth"


def main() -> None:
    svg, gt = main_mod.build()

    # Insert a black mask rectangle over PSV-101 + the V-101 / P-101A
    # discharge area, immediately before the closing </svg> tag so it
    # paints last (on top of everything).
    mask = (
        '<rect x="640" y="180" width="220" height="240" '
        'fill="#0a0a0a" stroke="#0a0a0a" />\n'
        '<text x="750" y="320" text-anchor="middle" '
        'font-family="Helvetica" font-size="18" fill="#444">'
        '— masked region —</text>'
    )
    svg = svg.replace("</svg>", f"{mask}\n</svg>")

    gt = dict(gt)
    gt["drawing_id"] = "01b"
    gt["title"] = "Crude Charge and Feed Section (occluded)"
    gt["drawing_no"] = "PID-CRUDE-FEED-001-OBS"
    # Anomaly flagging is baked in; the synthetic strands_pipeline cache
    # for 01b will report `verdict=needs_correction` + 3 self-correct
    # iterations + a final `pass` after PSV-101 is re-detected.
    # Obscured variant inherits the main drawing's intentional anomalies
    # (V-102, C-101 unprotected) AND adds the occlusion-recovery note so
    # the ISA-5.1 panel reflects what the self-correction loop solved.
    base = list(gt.get("expected_anomalies", []))
    base.append({
        "rule": "occluded_region_recovered",
        "severity": "low",
        "violated_by": "PSV-101",
        "description": "Black mask near P-101A discharge initially hid PSV-101; "
                       "recovered after one self-correction iteration.",
        "suggestion": "Original masked region resolved automatically.",
    })
    gt["expected_anomalies"] = base

    svg_path = SAMPLES / "01b_separator_pid_obscured.svg"
    pdf_path = SAMPLES / "01b_separator_pid_obscured.pdf"
    gt_path = GT / "01b_separator_pid_obscured.json"
    svg_path.write_text(svg, encoding="utf-8")
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(pdf_path))
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False))
    print(f"wrote {svg_path}")
    print(f"wrote {pdf_path}")
    print(f"wrote {gt_path}")


if __name__ == "__main__":
    main()
