"""Real accuracy evaluator — live extraction vs ground truth.

Unlike `benchmark/precision_recall.py` (which scores cached pipeline
JSON pre-built to match GT), this script:

  1. Calls `run_pipeline()` directly against the synthetic PDFs, which
     hits Bedrock Vision + Textract + Strands evaluator just like the
     production demo path.
  2. Computes tag-level precision/recall/F1 for equipment, instruments,
     and lines, plus a macro-F1 for each drawing.
  3. Optionally writes a JSON report and a one-line summary to stdout
     so the ralph-loop driver can grep on a single anchor.

Drawings considered (synthetic only — real samples have no GT):
  00 (super-complex refinery — main quality target)
  01 (separator hero)
  01b (occluded separator — exercises self-correction)

Usage:
  AWS_PROFILE=profile2 python3 scripts/eval_live_extraction.py
  AWS_PROFILE=profile2 python3 scripts/eval_live_extraction.py --drawing 00
  AWS_PROFILE=profile2 python3 scripts/eval_live_extraction.py --report-out
      .claude/artifacts/eval/live-eval-$(date +%s).json

Anti-cheating: this script reads ground_truth/*.json. Production code
(`backend/`) MUST NOT read those files. A separate static check in
scripts/check_no_gt_leak.py enforces that.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agents.strands_orchestrator import run_pipeline  # noqa: E402

GT_DIR = ROOT / "data" / "ground_truth"
SAMPLES = ROOT / "data" / "samples"
OUT_DIR = ROOT / ".claude" / "artifacts" / "eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DRAWINGS_WITH_GT = {
    "00":  ("00_complex_refinery.pdf",       "00_complex_refinery.json"),
    "01":  ("01_separator_pid.pdf",          "01_separator_pid.json"),
    "01b": ("01b_separator_pid_obscured.pdf", "01b_separator_pid_obscured.json"),
}


@dataclass(frozen=True)
class Counts:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 1.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _tags(items, key: str) -> set[str]:
    out: set[str] = set()
    for x in items:
        if isinstance(x, dict):
            v = x.get(key)
        else:
            v = getattr(x, key, None)
        if v:
            out.add(str(v).upper())
    return out


def _score(predicted: set[str], expected: set[str]) -> Counts:
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    return Counts(tp=tp, fp=fp, fn=fn)


def _eval_one(drawing_id: str) -> dict:
    pdf_name, gt_name = DRAWINGS_WITH_GT[drawing_id]
    pdf_path = SAMPLES / pdf_name
    gt_path = GT_DIR / gt_name
    if not pdf_path.exists() or not gt_path.exists():
        return {"drawing_id": drawing_id, "error": "missing pdf or gt"}

    started = time.time()
    result = run_pipeline(pdf_path, drawing_id=drawing_id)
    elapsed = round(time.time() - started, 2)

    gt = json.loads(gt_path.read_text())
    pred_eq = _tags(result.extraction.equipment, "tag")
    pred_inst = _tags(result.extraction.instruments, "tag")
    pred_lines = _tags(result.extraction.lines, "line_no")
    gt_eq = _tags(gt.get("equipment", []), "tag")
    gt_inst = _tags(gt.get("instruments", []), "tag")
    gt_lines = _tags(gt.get("lines", []), "line_no")

    eq = _score(pred_eq, gt_eq)
    inst = _score(pred_inst, gt_inst)
    lines = _score(pred_lines, gt_lines)
    macro_f1 = (eq.f1 + inst.f1 + lines.f1) / 3.0

    return {
        "drawing_id": drawing_id,
        "elapsed_s": elapsed,
        "verdict": result.critique.verdict,
        "iterations_used": (
            result.correction.iterations_used if result.correction else 0
        ),
        "equipment": {**asdict(eq), "f1": round(eq.f1, 4)},
        "instruments": {**asdict(inst), "f1": round(inst.f1, 4)},
        "lines": {**asdict(lines), "f1": round(lines.f1, 4)},
        "macro_f1": round(macro_f1, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drawing", choices=list(DRAWINGS_WITH_GT.keys()))
    ap.add_argument("--report-out", type=Path,
                    default=OUT_DIR / f"live-eval-{int(time.time())}.json")
    args = ap.parse_args()

    keys = [args.drawing] if args.drawing else list(DRAWINGS_WITH_GT.keys())
    rows: list[dict] = []
    for k in keys:
        print(f"=== eval {k} ===", flush=True)
        try:
            row = _eval_one(k)
        except Exception as exc:  # noqa: BLE001
            row = {"drawing_id": k, "error": repr(exc)}
        rows.append(row)
        if "error" in row:
            print(f"  {k}: ERROR {row['error']}")
        else:
            print(
                f"  {k}: macro_f1={row['macro_f1']:.4f}  "
                f"eq={row['equipment']['f1']:.3f} "
                f"inst={row['instruments']['f1']:.3f} "
                f"lines={row['lines']['f1']:.3f}  "
                f"({row['elapsed_s']}s, verdict={row['verdict']})"
            )

    completed = [r for r in rows if "macro_f1" in r]
    overall = (
        sum(r["macro_f1"] for r in completed) / len(completed)
        if completed else 0.0
    )
    summary = {"overall_macro_f1": round(overall, 4), "drawings": rows}
    args.report_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    # Single-line anchor for ralph-loop to grep on.
    print(f"\nOVERALL macro_f1={overall:.4f}  report={args.report_out}")
    return 0 if overall >= 0.0 else 1


if __name__ == "__main__":
    sys.exit(main())
