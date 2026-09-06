"""Precision/recall benchmark for the cached Strands pipeline outputs.

Compares each drawing's `*_strands_pipeline.json` extraction against the
ground-truth JSON in `data/ground_truth/`. Tag-level precision/recall is
computed for equipment, instruments, and lines.

This script reads ONLY cached artifacts — it never spends Bedrock tokens.
That keeps it suitable for CI / pre-recording verification.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / ".claude" / "artifacts" / "extraction"
GT_DIR = ROOT / "data" / "ground_truth"
OUT = ROOT / ".claude" / "artifacts" / "benchmark"
OUT.mkdir(parents=True, exist_ok=True)

DRAWINGS = {
    "01": "01_separator_pid.json",
    "01b": "01b_separator_pid_obscured.json",
    "02": "02_pump_hx_system.json",
    "03": "03_anomaly_demo.json",
}


@dataclass(frozen=True)
class Counts:
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _tags(items: Iterable[dict], key: str) -> set[str]:
    return {x[key] for x in items if x.get(key)}


def _score(predicted: set[str], expected: set[str]) -> Counts:
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    return Counts(tp=tp, fp=fp, fn=fn)


def _bench_one(key: str) -> dict:
    pipeline_path = ARTIFACTS / f"{key}_strands_pipeline.json"
    gt_path = GT_DIR / DRAWINGS[key]
    if not pipeline_path.exists():
        return {"drawing_id": key, "error": f"missing {pipeline_path.name}"}
    pipeline = json.loads(pipeline_path.read_text())
    gt = json.loads(gt_path.read_text())

    pred = pipeline["extraction"]
    eq = _score(_tags(pred["equipment"], "tag"), _tags(gt["equipment"], "tag"))
    inst = _score(_tags(pred["instruments"], "tag"), _tags(gt["instruments"], "tag"))
    lines = _score(_tags(pred["lines"], "line_no"), _tags(gt["lines"], "line_no"))

    return {
        "drawing_id": key,
        "verdict": pipeline.get("verdict"),
        "iterations_used": pipeline.get("iterations_used", 0),
        "total_elapsed_s": pipeline.get("total_elapsed_s"),
        "precision_recall": {
            "equipment": _to_dict(eq),
            "instruments": _to_dict(inst),
            "lines": _to_dict(lines),
        },
    }


def _to_dict(c: Counts) -> dict:
    return {
        "tp": c.tp, "fp": c.fp, "fn": c.fn,
        "precision": round(c.precision, 4),
        "recall": round(c.recall, 4),
        "f1": round(c.f1, 4),
    }


def _macro(rows: list[dict], kind: str, metric: str) -> float:
    values = [
        r["precision_recall"][kind][metric]
        for r in rows if "precision_recall" in r
    ]
    return round(sum(values) / len(values), 4) if values else 0.0


def main() -> None:
    rows = [_bench_one(k) for k in DRAWINGS]

    out_json = OUT / "precision_recall.json"
    out_md = OUT / "precision_recall.md"

    macro = {
        kind: {
            metric: _macro(rows, kind, metric)
            for metric in ("precision", "recall", "f1")
        }
        for kind in ("equipment", "instruments", "lines")
    }

    out_json.write_text(json.dumps({"per_drawing": rows, "macro": macro}, indent=2))

    md = ["# Precision / Recall — cached Strands pipeline\n"]
    md.append("Source: `.claude/artifacts/extraction/{key}_strands_pipeline.json`\n")
    md.append("Reference: `data/ground_truth/{...}.json`\n\n")
    md.append("## Per-drawing\n\n")
    md.append("| Drawing | Verdict | Iters | Elapsed | Eq P/R/F1 | Inst P/R/F1 | Line P/R/F1 |\n")
    md.append("|---|---|---|---|---|---|---|\n")
    for r in rows:
        if "error" in r:
            md.append(f"| {r['drawing_id']} | ERROR | - | - | - | - | - |\n")
            continue
        pr = r["precision_recall"]
        md.append(
            f"| {r['drawing_id']} | {r['verdict']} | {r['iterations_used']} | "
            f"{r['total_elapsed_s']:.1f}s | "
            f"{pr['equipment']['precision']}/{pr['equipment']['recall']}/{pr['equipment']['f1']} | "
            f"{pr['instruments']['precision']}/{pr['instruments']['recall']}/{pr['instruments']['f1']} | "
            f"{pr['lines']['precision']}/{pr['lines']['recall']}/{pr['lines']['f1']} |\n"
        )
    md.append("\n## Macro average across 4 drawings\n\n")
    md.append("| Kind | Precision | Recall | F1 |\n|---|---|---|---|\n")
    for kind in ("equipment", "instruments", "lines"):
        m = macro[kind]
        md.append(f"| {kind} | {m['precision']} | {m['recall']} | {m['f1']} |\n")
    out_md.write_text("".join(md))

    # Stdout summary
    print("=" * 60)
    print("Precision / Recall — cached Strands pipeline")
    print("=" * 60)
    for r in rows:
        if "error" in r:
            print(f"{r['drawing_id']}: {r['error']}")
            continue
        pr = r["precision_recall"]
        print(
            f"{r['drawing_id']:<4} verdict={r['verdict']:<18} "
            f"iter={r['iterations_used']} elapsed={r['total_elapsed_s']:>6.1f}s"
        )
        for kind in ("equipment", "instruments", "lines"):
            c = pr[kind]
            print(
                f"  {kind:<12} P={c['precision']:.3f} R={c['recall']:.3f} F1={c['f1']:.3f} "
                f"(tp={c['tp']} fp={c['fp']} fn={c['fn']})"
            )
    print()
    print("Macro average:")
    for kind in ("equipment", "instruments", "lines"):
        m = macro[kind]
        print(f"  {kind:<12} P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}")
    print()
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")


if __name__ == "__main__":
    main()
