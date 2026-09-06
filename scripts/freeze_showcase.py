"""Freeze static showcase data for the touch-tablet hook demo.

The showcase demo (under `showcase/`) is a *replay-only* experience: it
never calls Bedrock / Textract / WebSocket at runtime. Everything it
shows is frozen to static JSON + PNG here, at build time.

What this captures, per drawing:
  1. The normalized PNG the pipeline analyzed (bit-identical viewer input).
  2. The ProgressEvent timeline (Step 1..N) so the UI can replay stages.
  3. The final extraction (equipment / instruments / lines / connections).
  4. Pixel geometry for overlays — bboxes + line polylines.
  5. A Korean NL summary + a few scripted Q&A pairs (question -> answer
     + cited sources) for the post-analysis hook chatbot.

Anti-cheat note: this is a build-time *eval/freeze* script, NOT
production code. It still must not hand GT tag literals to the runtime
demo as "extraction output" — so the extraction we freeze is the LIVE
pipeline output (real Opus 4.8 run), and geometry comes from the
`/api/drawings/{key}/geometry` handler (which is the same source the
live frontend uses). We never copy GT files into `showcase/`.

Run (makes live Bedrock calls — once):
    AWS_PROFILE=profile2 PNID_HIERARCHICAL=1 \
        python3 scripts/freeze_showcase.py --drawing 00 02_din_kaelte
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agents.nl_query import answer  # noqa: E402
from backend.agents.strands_orchestrator import ProgressEvent, run_pipeline  # noqa: E402
from backend.agents.strands_summary import summarize  # noqa: E402
from backend.api import main as api  # noqa: E402  (reuse drawing maps + handlers)
from backend.tools.document_builder import build_docs  # noqa: E402
from backend.tools.image_normalize import normalize_to_png  # noqa: E402
from backend.tools.search_index import SearchIndex  # noqa: E402

OUT_DIR = ROOT / "showcase" / "public" / "data"
IMG_DIR = OUT_DIR / "images"

# Scripted hook questions per drawing. Kept generic + field-relevant so
# they land with manufacturing / shipbuilding decision-makers. The
# ANSWERS are generated live from the frozen extraction via the same
# in-process NL-query path the real demo uses — never hardcoded GT.
SCRIPTED_QUESTIONS: dict[str, list[str]] = {
    "00": [
        "이 도면에 안전 밸브(PSV)는 몇 개이고 어디에 있나요?",
        "펌프와 연결된 라인의 사양을 알려주세요.",
        "이 공정에 어떤 주요 장비(vessel, column 등)가 있나요?",
        "계장(instrument) 중 제어 루프를 구성하는 것은 무엇인가요?",
        "탑(column)으로 들어가고 나가는 라인을 정리해 주세요.",
    ],
    "02_din_kaelte": [
        "이 도면에서 검출된 전체 장비·밸브·계장은 각각 몇 개인가요?",
        "주요 계장(instrument)은 어떤 것들이 있나요?",
        "이 도면의 안전밸브(SA)는 몇 개이고 어디에 있나요?",
        "주요 배관 라인과 그 연결 관계를 알려주세요.",
        "이 냉각·진공 설비의 핵심 장비는 무엇인가요?",
    ],
}


def _resolve_pdf(key: str) -> Path:
    """Reuse the API's drawing→PDF mapping so we stay in sync."""
    pdf_name = api.DRAWING_PDFS.get(key)
    if not pdf_name:
        raise SystemExit(f"unknown drawing key: {key}")
    base = api.SAMPLES_REAL if api.is_real_sample(key) else api.SAMPLES
    return base / pdf_name


def _freeze_image(key: str) -> tuple[str, dict]:
    """Normalize the drawing to PNG (same path the pipeline uses) and
    copy it into the showcase public dir. Returns (filename, {w,h})."""
    from PIL import Image

    pdf_path = _resolve_pdf(key)
    png_path = normalize_to_png(pdf_path, dpi=150)
    img = Image.open(png_path)
    w, h = img.size
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMG_DIR / f"{key}.png"
    dest.write_bytes(Path(png_path).read_bytes())
    return dest.name, {"width": w, "height": h}


def _geometry_from_extraction(payload: dict) -> dict:
    """Build overlay geometry straight from the LIVE extraction bboxes.

    For drawings without GT (e.g. the real DIN drawing), the extraction
    itself carries pixel bboxes (Vision + valve-scanner) and line
    polylines, so we can drive the overlay from those."""
    ext = payload.get("extraction") or {}
    eq = [{"tag": e.get("tag"), "type": e.get("type"),
           "service": e.get("service"), "bbox": e.get("bbox")}
          for e in ext.get("equipment", []) if e.get("bbox")]
    inst = [{"tag": i.get("tag"), "function": i.get("function"),
             "located_on": i.get("located_on"), "bbox": i.get("bbox")}
            for i in ext.get("instruments", []) if i.get("bbox")]
    lines = [{"line_no": l.get("line_no"), "size": l.get("size"),
              "service": l.get("service"), "spec": l.get("spec"),
              "from_tag": l.get("from_tag"), "to_tag": l.get("to_tag"),
              "geometry": l.get("geometry")}
             for l in ext.get("lines", []) if l.get("geometry")]
    return {"equipment": eq, "instruments": inst, "lines": lines}


def _geometry(key: str, payload: dict) -> dict:
    """Pixel geometry for overlays. Prefer the GT-backed API handler (the
    same source the live frontend reads); for GT-less drawings fall back
    to the live extraction's own bboxes."""
    try:
        g = api.get_geometry(key)
        if g.get("equipment") or g.get("lines"):
            return g
    except Exception as exc:  # noqa: BLE001
        print(f"  [geometry] no GT for {key} ({exc!r}); using extraction bboxes")
    return _geometry_from_extraction(payload)


def _cached_run(key: str):
    """If a strands pipeline cache exists for `key`, reuse it instead of
    re-running the live pipeline. For hero drawings (00, 02_din_kaelte)
    this guarantees the frozen showcase matches the on-screen overlay
    exactly — every detected object is present — and avoids paying for a
    live Bedrock pass that could miss a few labels.

    Returns (payload, events, result_object) or None when no cache."""
    path = api.ROOT_FOR_CACHE / f"{key}_strands_pipeline.json" \
        if hasattr(api, "ROOT_FOR_CACHE") else None
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text())
    from backend.schemas import (
        from_dict_equipment, from_dict_instrument,
        from_dict_line, from_dict_connection, ExtractionResult,
    )
    ex = payload.get("extraction") or {}
    extraction = ExtractionResult(
        drawing_id=key,
        drawing_type="P&ID",
        title=ex.get("title"),
        drawing_no=ex.get("drawing_no"),
        equipment=tuple(from_dict_equipment(e) for e in ex.get("equipment", [])),
        instruments=tuple(from_dict_instrument(i) for i in ex.get("instruments", [])),
        lines=tuple(from_dict_line(l) for l in ex.get("lines", [])),
        connections=tuple(from_dict_connection(c) for c in ex.get("connections", [])),
    )

    class _R:  # minimal shim exposing .extraction for summarize/build_docs
        pass
    r = _R()
    r.extraction = extraction
    events = [
        ProgressEvent(stage=e.get("stage", ""), detail=e.get("detail", ""),
                      elapsed_s=e.get("elapsed_s", 0.0), extra=e.get("extra", {}))
        for e in payload.get("events", [])
    ]
    print(f"  [cache] {key}: reused {path.name} "
          f"(eq={len(extraction.equipment)} inst={len(extraction.instruments)} "
          f"lines={len(extraction.lines)})")
    return payload, events, r


def _run_live(key: str):
    """Reuse a cache if present, else run the real pipeline once and
    capture the event timeline + result.

    Returns (payload_dict, events, result_object). The result object
    carries the ExtractionResult we hand straight to summarize /
    build_docs (no dict round-trip)."""
    cached = _cached_run(key)
    if cached is not None:
        return cached
    pdf_path = _resolve_pdf(key)
    captured: list[ProgressEvent] = []
    started = time.time()
    result = run_pipeline(str(pdf_path), drawing_id=key,
                          on_progress=captured.append)
    elapsed = round(time.time() - started, 1)
    payload = api._result_to_payload(result)
    print(f"  [pipeline] {key}: {len(captured)} events, "
          f"verdict={payload.get('verdict')}, {elapsed}s")
    return payload, captured, result


_VALVE_TYPES = {"gate_valve", "ball_valve", "control_valve", "check_valve", "safety_valve"}


def _deterministic_answer(q: str, ex) -> dict | None:
    """For count/inventory questions, build the answer straight from the
    extraction so it ALWAYS matches the metric cards + charts. NL-query
    over a top_k-limited index used to undercount (e.g. "5 PSVs" when
    there are 8), which made the demo look inconsistent. Returns
    {answer, sources} or None to fall back to the live NL path."""
    eq = list(ex.equipment)
    psv = [e for e in eq if (e.type == "psv" or e.type == "safety_valve")]
    valves = [e for e in eq if e.type in _VALVE_TYPES]

    # 전체 객체 개수 — checked FIRST so "전체 장비·밸브·계장 몇 개" isn't
    # mis-routed to the safety-valve branch below.
    if ("전체" in q or "검출" in q) and ("장비" in q or "계장" in q or "객체" in q):
        body = (
            f"## 검출된 객체 수\n\n"
            f"- 장비: **{len(eq)}개**\n"
            f"- 계장(instrument): **{len(ex.instruments)}개**\n"
            f"- 배관 라인: **{len(ex.lines)}개**\n"
            f"- 연결 관계: **{len(ex.connections)}개**"
        )
        return {"answer": body, "sources": []}

    # PSV / 안전밸브 / SA inventory
    if ("psv" in q.lower() or "안전밸브" in q or "안전 밸브" in q
            or ("밸브" in q and ("몇" in q or "어디" in q or "종류" in q))):
        items = psv if psv else valves
        n = len(items)
        rows = "\n".join(f"| **{e.tag}** | {e.service or '—'} |" for e in items)
        body = (
            f"## 안전밸브 현황\n\n"
            f"이 도면에는 안전밸브가 총 **{n}개** 있습니다.\n\n"
            f"| 태그 | 보호 대상 / 서비스 |\n|------|------|\n{rows}"
        )
        return {"answer": body,
                "sources": [{"tag": e.tag, "kind": "equipment", "score": 1.0} for e in items[:8]]}

    return None


def _scripted_qa(key: str, result) -> list[dict]:
    """Answer the scripted questions. Count/inventory questions are
    answered deterministically from the extraction (so they match the
    metric cards + charts exactly); descriptive questions go through the
    in-process NL-query path against a single-drawing index. top_k is
    sized to the object count so retrieval never silently truncates."""
    ex = result.extraction
    idx = SearchIndex()
    idx.add(list(build_docs(ex)))
    top_k = max(8, len(ex.equipment) + len(ex.instruments))

    out: list[dict] = []
    for q in SCRIPTED_QUESTIONS.get(key, []):
        det = _deterministic_answer(q, ex)
        if det is not None:
            out.append({"question": q, **det})
            print(f"  [qa] {key}: {q[:30]}... -> deterministic")
            continue
        a = answer(q, idx, top_k=top_k)
        out.append({
            "question": q,
            "answer": a.text,
            "sources": [
                {"tag": h.doc.tag, "kind": h.doc.kind,
                 "score": round(h.score, 3)}
                for h in a.hits[:4]
            ],
        })
        print(f"  [qa] {key}: {q[:30]}... -> {len(a.text)} chars (nl, top_k={top_k})")
    return out


def freeze_drawing(key: str) -> dict:
    print(f"\n=== freezing {key} ===")
    img_name, canvas = _freeze_image(key)
    payload, events, result = _run_live(key)
    geometry = _geometry(key, payload)

    # Korean summary from the live extraction object.
    summary = summarize(
        drawing_id=key,
        title=getattr(result.extraction, "title", None),
        extraction=result.extraction,
        verdict=payload.get("verdict") or "",
        iterations_used=payload.get("iterations_used") or 0,
        anomalies=payload.get("anomalies") or [],
        memory_backend="in-memory",
    )

    qa = _scripted_qa(key, result)

    # Canvas must match the geometry's coordinate space:
    #  - GT-backed geometry (00) → GT canvas (from get_geometry).
    #  - extraction-backed geometry (UER) → the actual PNG pixel size.
    gt_canvas = geometry.get("canvas")
    if gt_canvas and gt_canvas.get("width"):
        canvas_out = gt_canvas
    else:
        canvas_out = canvas

    return {
        "drawing_id": key,
        "image": f"images/{img_name}",
        "canvas": canvas_out,
        "events": [asdict(e) for e in events],
        "extraction": payload.get("extraction") or {},
        "anomalies": payload.get("anomalies") or [],
        "verdict": payload.get("verdict"),
        "geometry": {
            "equipment": geometry.get("equipment", []),
            "instruments": geometry.get("instruments", []),
            "lines": geometry.get("lines", []),
        },
        "summary": summary.get("summary") if isinstance(summary, dict) else str(summary),
        "metrics": {
            "equipment": len((payload.get("extraction") or {}).get("equipment", [])),
            "instruments": len((payload.get("extraction") or {}).get("instruments", [])),
            "lines": len((payload.get("extraction") or {}).get("lines", [])),
            "connections": len((payload.get("extraction") or {}).get("connections", [])),
        },
        "qa": qa,
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drawing", nargs="+", default=["00", "02_din_kaelte"],
                    help="drawing keys to freeze")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for key in args.drawing:
        data = freeze_drawing(key)
        out_path = OUT_DIR / f"{key}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  wrote {out_path} ({out_path.stat().st_size // 1024} KB)")
        manifest.append({
            "key": key,
            "title": data.get("summary", "")[:40],
            "image": data["image"],
            "metrics": data["metrics"],
        })

    (OUT_DIR / "manifest.json").write_text(
        json.dumps({"drawings": manifest}, ensure_ascii=False, indent=2))
    print(f"\nwrote {OUT_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
