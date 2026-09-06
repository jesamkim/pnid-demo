"""Run the Vision Extractor on the four demo P&IDs and persist the results.

Usage: python3 scripts/verify_extractor.py [--drawing 01|01b|02|03|all]
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
from backend.tools.pdf_renderer import render_page

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "data" / "samples"
GT = ROOT / "data" / "ground_truth"
OUT = ROOT / ".claude" / "artifacts" / "extraction"
OUT.mkdir(parents=True, exist_ok=True)

DRAWINGS = {
    "01": ("01_separator_pid.pdf", "01_separator_pid.json", "Three-Phase Separator with Liquid Pumps and Cooler"),
    "01b": ("01b_separator_pid_obscured.pdf", "01b_separator_pid_obscured.json", "Same separator but a region is obscured"),
    "02": ("02_pump_hx_system.pdf", "02_pump_hx_system.json", "Feed pump set with steam preheater"),
    "03": ("03_anomaly_demo.pdf", "03_anomaly_demo.json", "Flash drum with intentional issues"),
}


def _to_jsonable(r):
    return {
        "drawing_id": r.drawing_id,
        "drawing_type": r.drawing_type,
        "title": r.title,
        "drawing_no": r.drawing_no,
        "equipment": [asdict(e) for e in r.equipment],
        "instruments": [asdict(i) for i in r.instruments],
        "lines": [asdict(l) for l in r.lines],
        "connections": [asdict(c) for c in r.connections],
    }


def run_one(key: str) -> dict:
    pdf_name, gt_name, hint = DRAWINGS[key]
    pdf_path = SAMPLES / pdf_name
    print(f"\n=== Drawing {key}: {pdf_name} ===")

    img = render_page(pdf_path, page=0, dpi=200)
    print(f"  rendered {img.size}")

    t0 = time.time()
    extracted, meta = extract_from_image(
        image=img,
        drawing_id=key,
        context_hint=hint,
        use_secondary=False,
    )
    elapsed = time.time() - t0

    out_json = OUT / f"{key}_extracted.json"
    out_meta = OUT / f"{key}_meta.json"
    out_json.write_text(json.dumps(_to_jsonable(extracted), indent=2))
    out_meta.write_text(json.dumps({k: v for k, v in meta.items() if k != "raw_text"}, indent=2))
    (OUT / f"{key}_raw.txt").write_text(meta["raw_text"])

    gt_raw = json.loads((GT / gt_name).read_text())
    summary = {
        "drawing": key,
        "elapsed_s": round(elapsed, 1),
        "in_tok": meta["input_tokens"],
        "out_tok": meta["output_tokens"],
        "extracted": {
            "equipment": len(extracted.equipment),
            "instruments": len(extracted.instruments),
            "lines": len(extracted.lines),
            "connections": len(extracted.connections),
        },
        "ground_truth": {
            "equipment": len(gt_raw.get("equipment", [])),
            "instruments": len(gt_raw.get("instruments", [])),
            "lines": len(gt_raw.get("lines", [])),
            "connections": len(gt_raw.get("connections", [])),
        },
    }
    print(f"  elapsed={elapsed:.1f}s  in_tok={meta['input_tokens']}  out_tok={meta['output_tokens']}")
    print(f"  extracted: {summary['extracted']}")
    print(f"  ground_truth: {summary['ground_truth']}")
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--drawing", default="01", choices=["01", "01b", "02", "03", "all"])
    args = p.parse_args()

    keys = list(DRAWINGS.keys()) if args.drawing == "all" else [args.drawing]
    summaries = [run_one(k) for k in keys]

    print("\n=== SUMMARY ===")
    for s in summaries:
        e = s["extracted"]; g = s["ground_truth"]
        print(f"  {s['drawing']:>4}  Eq {e['equipment']:>2}/{g['equipment']:<2}  Inst {e['instruments']:>2}/{g['instruments']:<2}  "
              f"Lines {e['lines']:>2}/{g['lines']:<2}  Conn {e['connections']:>2}/{g['connections']:<2}  "
              f"elapsed={s['elapsed_s']}s tokens={s['in_tok']}/{s['out_tok']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
