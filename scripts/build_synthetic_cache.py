"""Build synthetic strands_pipeline.json files from ground-truth JSON.

This script lets the demo run end-to-end on cached data without spending
Bedrock tokens. The output mirrors the shape of a real Strands
orchestrator run (events list, verdict, iterations_used, anomalies)
so the React replay UI behaves identically to a live extraction.

Usage:
    python3 scripts/build_synthetic_cache.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT_DIR = ROOT / "data" / "ground_truth"
OUT_DIR = ROOT / ".claude" / "artifacts" / "extraction"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _events_pass(eq: int, inst: int, lines: int, conn: int) -> tuple[list[dict], float]:
    """Synthetic event sequence for a clean (verdict=pass) extraction."""
    events = [
        {
            "stage": "render",
            "detail": "01_separator_pid.pdf -> 5625x3334 @ 200dpi",
            "elapsed_s": 0.18,
            "extra": {},
        },
        {
            "stage": "extract",
            "detail": f"Eq={eq} Inst={inst} Lines={lines} Conn={conn}",
            "elapsed_s": 18.7,
            "extra": {"input_tokens": 5460, "output_tokens": 2117},
        },
        {
            "stage": "evaluate",
            "detail": "verdict=pass rule_anomalies=0 llm_findings=0",
            "elapsed_s": 3.1,
            "extra": {},
        },
        {
            "stage": "finalize",
            "detail": "anomalies=0",
            "elapsed_s": 0.0,
            "extra": {},
        },
    ]
    total = sum(e["elapsed_s"] for e in events)
    return events, round(total, 2)


def _events_self_correct(eq: int, inst: int, lines: int, conn: int) -> tuple[list[dict], float]:
    """Synthetic events for an occluded run that self-corrects in 1 iteration.

    Story arc:
      1. initial extract misses PSV-101 (eq-1)
      2. ISA evaluator flags vessel_without_psv_protection
      3. error analyzer identifies occlusion
      4. strategy planner schedules a focused re-extract
      5. re-extract finds PSV-101 (correct count)
      6. re-evaluate -> pass
    """
    initial_eq = eq - 1
    events = [
        {
            "stage": "render",
            "detail": "01b_separator_pid_obscured.pdf -> 5625x3334 @ 200dpi",
            "elapsed_s": 0.19,
            "extra": {},
        },
        {
            "stage": "extract",
            "detail": f"Eq={initial_eq} Inst={inst} Lines={lines} Conn={conn-1}",
            "elapsed_s": 19.4,
            "extra": {"input_tokens": 5460, "output_tokens": 1928},
        },
        {
            "stage": "evaluate",
            "detail": (
                "verdict=needs_correction rule_anomalies=1 llm_findings=1 "
                "(vessel_without_psv_protection on V-101 + occluded region)"
            ),
            "elapsed_s": 5.7,
            "extra": {},
        },
        {
            "stage": "self_correct_initial_extract",
            "detail": f"Eq={initial_eq} Inst={inst} Lines={lines} (snapshot)",
            "elapsed_s": 0.0,
            "extra": {"iteration": 0, "verdict_after": "needs_correction"},
        },
        {
            "stage": "self_correct_error_analysis",
            "detail": (
                "strategy=rerun_with_focus_on_occluded_region; "
                "root_cause=A solid black rectangle near P-101A discharge "
                "occludes the upper-left region where PSV-101 is expected."
            ),
            "elapsed_s": 3.6,
            "extra": {"iteration": 1, "verdict_after": ""},
        },
        {
            "stage": "self_correct_reextract",
            "detail": (
                "strategy=rerun_with_focus_on_occluded_region; "
                f"new Eq={eq} Inst={inst} Lines={lines} (PSV-101 recovered)"
            ),
            "elapsed_s": 14.8,
            "extra": {"iteration": 1, "verdict_after": ""},
        },
        {
            "stage": "self_correct_re_evaluate",
            "detail": "rule_anomalies=0 llm_findings=0",
            "elapsed_s": 4.2,
            "extra": {"iteration": 1, "verdict_after": "pass"},
        },
        {
            "stage": "self_correct_done",
            "detail": "iterations=1 final_verdict=pass",
            "elapsed_s": 22.6,
            "extra": {},
        },
        {
            "stage": "finalize",
            "detail": "anomalies=0",
            "elapsed_s": 0.0,
            "extra": {},
        },
    ]
    total = sum(e["elapsed_s"] for e in events if e["stage"] != "self_correct_done")
    return events, round(total, 2)


def _shape_from_gt(gt: dict) -> dict:
    """Reshape ground_truth into the ExtractionResult JSON shape."""
    return {
        "equipment": [
            {"tag": e["tag"], "type": e["type"], "service": e.get("service"),
             "bbox": e.get("bbox"), "page": 1, "properties": {}}
            for e in gt["equipment"]
        ],
        "instruments": [
            {"tag": i["tag"], "function": i["function"], "loop_id": i["loop_id"],
             "located_on": i.get("located_on"), "bbox": i.get("bbox"), "page": 1}
            for i in gt["instruments"]
        ],
        "lines": [
            {
                "line_no": l["line_no"], "size": l.get("size"),
                "service": l.get("service"), "spec": l.get("spec"),
                "from_tag": l.get("from_tag"), "to_tag": l.get("to_tag"),
                "geometry": l.get("geometry"),
                "page": 1,
            }
            for l in gt["lines"]
        ],
        "connections": [
            {"from_tag": c["from_tag"], "to_tag": c["to_tag"],
             "type": c.get("type", "pipe"), "via_line": c.get("via_line")}
            for c in gt.get("connections", [])
        ],
    }


def _build(key: str, gt_filename: str, *, kind: str) -> None:
    gt = json.loads((GT_DIR / gt_filename).read_text())
    extraction = _shape_from_gt(gt)
    eq = len(extraction["equipment"])
    inst = len(extraction["instruments"])
    lines = len(extraction["lines"])
    conn = len(extraction["connections"])
    # Anomalies come from `expected_anomalies` in the GT JSON so the
    # demo's ISA-5.1 panel always has visible findings.
    expected = list(gt.get("expected_anomalies", []))
    if kind == "pass":
        events, total = _events_pass(eq, inst, lines, conn)
        # Even a "pass" run reports the rule findings post-finalize.
        verdict = "pass" if not expected else "needs_correction"
        iterations = 0
        anomalies = expected
    elif kind == "self_correct":
        events, total = _events_self_correct(eq, inst, lines, conn)
        verdict = "pass" if not expected else "needs_correction"
        iterations = 1
        anomalies = expected
    else:
        raise ValueError(kind)

    payload = {
        "drawing_id": key,
        "verdict": verdict,
        "iterations_used": iterations,
        "total_elapsed_s": total,
        "extraction": extraction,
        "anomalies": anomalies,
        "events": events,
        "synthesized_at": time.time(),
        "synthetic": True,
    }
    out = OUT_DIR / f"{key}_strands_pipeline.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"wrote {out} (verdict={verdict}, iters={iterations}, "
          f"events={len(events)}, eq={eq} inst={inst} lines={lines})")


def main() -> None:
    _build("01", "01_separator_pid.json", kind="pass")
    _build("01b", "01b_separator_pid_obscured.json", kind="self_correct")
    # DIN EN 10628 synthetic drawing — hero so it replays instantly with
    # 100% object recognition (GT == extraction). self_correct gives the
    # demo a richer multi-iteration story + visible rule findings.
    _build("02_din_kaelte", "02_din_kaelte.json", kind="self_correct")
    # Remove stale caches for the deprecated 02 / 03 drawings.
    for stale in ("03",):
        for suffix in ("_strands_pipeline.json", "_pipeline.json"):
            p = OUT_DIR / f"{stale}{suffix}"
            if p.exists():
                p.unlink()
                print(f"removed stale {p}")


if __name__ == "__main__":
    main()
