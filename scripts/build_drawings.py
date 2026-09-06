"""Regenerate every demo drawing from its topology spec.

For each topology module:
  1. build TopologySpec
  2. run auto_layout.build_layout → SVG + ground_truth
  3. paint optional post-render overlay (e.g. obscured mask)
  4. write SVG, PDF (cairosvg), and ground_truth JSON
  5. update the synthetic strands_pipeline cache
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cairosvg  # noqa: E402

from data.synthesis.auto_layout import build_layout  # noqa: E402
SAMPLES = ROOT / "data" / "samples"
GT_DIR = ROOT / "data" / "ground_truth"
SAMPLES.mkdir(parents=True, exist_ok=True)
GT_DIR.mkdir(parents=True, exist_ok=True)


# (drawing_id, topology_module, sample_pdf_basename, gt_basename, post_render_hook?)
DRAWINGS = [
    ("00",  "data.synthesis.topo_complex_refinery",
        "00_complex_refinery",     "00_complex_refinery",     None),
    ("01",  "data.synthesis.topo_crude_unit",
        "01_separator_pid",        "01_separator_pid",        None),
    ("01b", "data.synthesis.topo_crude_unit_obscured",
        "01b_separator_pid_obscured", "01b_separator_pid_obscured",
        "mask_overlay_svg"),
    ("02",  "data.synthesis.topo_ngl_fractionation",
        "02_ngl_fractionation",    "02_ngl_fractionation",    None),
    ("03",  "data.synthesis.topo_compressor_station",
        "03_compressor_station",   "03_compressor_station",   None),
    ("04",  "data.synthesis.topo_amine_treater",
        "04_amine_treater",        "04_amine_treater",        None),
    # DIN EN 10628 synthetic drawing (refrigeration + vacuum station) —
    # German tags/services, drawing-00 complexity, full ground truth.
    ("02_din_kaelte", "data.synthesis.topo_din_kaelte",
        "02_din_kaelte",           "02_din_kaelte",           None),
]


def _splice_overlay(svg: str, overlay: str) -> str:
    return svg.replace("</svg>", f"{overlay}\n</svg>")


def main() -> None:
    for drawing_id, mod_path, pdf_base, gt_base, hook_attr in DRAWINGS:
        mod = importlib.import_module(mod_path)
        spec = mod.build()
        result = build_layout(spec)
        svg = result.svg
        if hook_attr:
            overlay = getattr(mod, hook_attr)()
            svg = _splice_overlay(svg, overlay)
        svg_path = SAMPLES / f"{pdf_base}.svg"
        pdf_path = SAMPLES / f"{pdf_base}.pdf"
        gt_path = GT_DIR / f"{gt_base}.json"
        svg_path.write_text(svg, encoding="utf-8")
        cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(pdf_path))
        gt_path.write_text(json.dumps(result.ground_truth, indent=2, ensure_ascii=False))
        eq = len(result.ground_truth["equipment"])
        ins = len(result.ground_truth["instruments"])
        ln = len(result.ground_truth["lines"])
        print(f"  {drawing_id:<4} → {pdf_base} ({eq} eq / {ins} inst / {ln} lines)")


if __name__ == "__main__":
    main()
