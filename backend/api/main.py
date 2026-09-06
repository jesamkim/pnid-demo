"""FastAPI entry point for the P&ID demo UI backend.

Routes:
  GET   /api/health                          — liveness + drawing keys
  GET   /api/drawings                        — list demo drawings (cached)
  GET   /api/drawings/{key}/pipeline         — cached pipeline result
  GET   /api/drawings/{key}/image            — PNG render of the drawing
  POST  /api/search                          — hybrid search over indexed docs
  POST  /api/query                           — Strands NL query (Sonnet 4.6)
  GET   /api/memory/{session_id}             — list extractions saved this session
  GET   /api/memory/{session_id}/{drawing}   — recall one extraction
  WS    /api/ws/extract/{key}                — live Strands pipeline progress

The Strands orchestrator is the single source of truth for live extraction;
cached `cached_runs` are pre-baked results from `scripts/verify_strands_pipeline.py`
so the UI works on cold start without spending Bedrock tokens.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import boto3

ROOT_FOR_CACHE = Path(__file__).resolve().parent.parent.parent / ".claude" / "artifacts" / "extraction"

from fastapi import (
    FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.agents.agentcore_harness_client import (
    HarnessClient,
    get_default_harness_client,
)
from backend.agents.agentcore_runtime_client import (
    AgentCoreRuntimeClient,
    AgentCoreRuntimeNotConfigured,
)
from backend.agents.memory_store import (
    AgentCoreStore,
    MemoryStore,
    get_default_store,
)
from backend.agents.strands_nl_query import answer
from backend.agents.strands_orchestrator import ProgressEvent, run_pipeline
from backend.api.state import (
    DRAWING_GROUND_TRUTH, DRAWING_KEYS, DRAWING_PDFS, DRAWING_SOURCES,
    DRAWING_TITLES, GROUND_TRUTH, HERO_KEYS, PRESTAGED_KEYS, REAL_KEYS,
    SAMPLES, SAMPLES_REAL, has_ground_truth, is_real_sample, state,
)
from backend.api.uploads import (
    UnsupportedUploadType, UploadTooLarge, get_registry,
)
from backend.config import get_settings
from backend.tools.pdf_renderer import render_page

app = FastAPI(title="P&ID Agentic Demo", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # demo; restrict via CloudFront in prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


_DEFAULT_ACTOR = "demo-presenter"

_MEMORY: Optional[MemoryStore] = None
_AGENTCORE: Optional[AgentCoreRuntimeClient] = None


def _agentcore() -> Optional[AgentCoreRuntimeClient]:
    """Return the AgentCore Runtime client if configured, else None.

    Memoised across requests; the first failed lookup is also cached so
    the in-process fallback path stays hot during the demo when no
    BEDROCK_AGENTCORE_RUNTIME_ARN is set.
    """
    global _AGENTCORE
    if _AGENTCORE is not None:
        return _AGENTCORE
    try:
        _AGENTCORE = AgentCoreRuntimeClient()
        return _AGENTCORE
    except AgentCoreRuntimeNotConfigured:
        return None


def _set_agentcore_for_test(client: Optional[AgentCoreRuntimeClient]) -> None:
    global _AGENTCORE
    _AGENTCORE = client


def _memory() -> MemoryStore:
    global _MEMORY
    if _MEMORY is not None:
        return _MEMORY
    memory_id = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
    if memory_id:
        _MEMORY = AgentCoreStore(
            memory_id=memory_id, region_name=get_settings().aws_region,
        )
    else:
        _MEMORY = get_default_store()
    return _MEMORY


def _set_memory_for_test(store: MemoryStore) -> None:
    global _MEMORY
    _MEMORY = store


def _result_to_payload(result) -> dict:
    return {
        "drawing_id": result.drawing_id,
        "verdict": result.critique.verdict,
        "iterations_used": result.correction.iterations_used if result.correction else 0,
        "total_elapsed_s": result.total_elapsed_s,
        "extraction": {
            "equipment": [asdict(e) for e in result.extraction.equipment],
            "instruments": [asdict(i) for i in result.extraction.instruments],
            "lines": [asdict(l) for l in result.extraction.lines],
            "connections": [asdict(c) for c in result.extraction.connections],
        },
        "anomalies": [asdict(a) for a in result.anomalies],
        "events": [asdict(e) for e in result.events],
    }


def _memory_summary(payload: dict) -> dict:
    extraction = payload.get("extraction") or {}
    return {
        "verdict": payload.get("verdict"),
        "iterations_used": payload.get("iterations_used"),
        "total_elapsed_s": payload.get("total_elapsed_s"),
        "counts": {
            "equipment": len(extraction.get("equipment") or []),
            "instruments": len(extraction.get("instruments") or []),
            "lines": len(extraction.get("lines") or []),
            "connections": len(extraction.get("connections") or []),
        },
        "anomaly_count": len(payload.get("anomalies") or []),
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "drawings": DRAWING_KEYS,
        "memory_backend": "agentcore" if os.getenv("BEDROCK_AGENTCORE_MEMORY_ID") else "in-memory",
    }


@app.get("/api/drawings")
def list_drawings() -> dict:
    """List both hero (cached) and pre-staged (live-then-cached) drawings.

    Returns one entry per `DRAWING_KEYS`, even if the strands_pipeline
    cache is missing (pre-staged drawings before their first live run
    look like "?" badges in the UI). The `kind` field tells the SPA
    which sidebar group to put each drawing in.
    """
    state().ensure_index()
    out = []
    for k in DRAWING_KEYS:
        run = state().cached_runs.get(k)
        if k in HERO_KEYS:
            kind = "hero"
        elif k in REAL_KEYS:
            kind = "real"
        else:
            kind = "prestaged"
        entry: dict = {
            "key": k,
            "pdf": DRAWING_PDFS[k],
            "title": DRAWING_TITLES.get(k, k),
            "kind": kind,
            "has_cache": run is not None and not is_real_sample(k),
            "has_ground_truth": has_ground_truth(k),
            "source": DRAWING_SOURCES.get(k),
        }
        if run is not None:
            ex = run.pipeline_dump.get("extraction", {})
            entry.update({
                "verdict": run.pipeline_dump.get("verdict"),
                "iterations_used": run.pipeline_dump.get("iterations_used", 0),
                "counts": {
                    "equipment": len(ex.get("equipment", [])),
                    "instruments": len(ex.get("instruments", [])),
                    "lines": len(ex.get("lines", [])),
                    "anomalies": len(run.pipeline_dump.get("anomalies", [])),
                },
            })
        else:
            entry.update({
                "verdict": None,
                "iterations_used": 0,
                "counts": {"equipment": 0, "instruments": 0,
                            "lines": 0, "anomalies": 0},
            })
        out.append(entry)
    return {"drawings": out}


@app.get("/api/drawings/{key}/pipeline")
def get_pipeline(key: str) -> dict:
    state().ensure_index()
    run = state().cached_runs.get(key)
    if not run:
        raise HTTPException(404, f"drawing {key} not found")
    return run.pipeline_dump


@app.get("/api/drawings/{key}/geometry")
def get_geometry(key: str) -> dict:
    """Synthetic-PID geometry for the canvas overlay.

    Sources from `data/ground_truth/*.json` so the UI can draw bounding
    boxes and traveling-light line segments. The LLM extraction itself
    does not produce reliable pixel coordinates yet (Phase 4 work),
    so for the demo we surface the ground-truth geometry and label it
    as such in the response payload.
    """
    fname = DRAWING_GROUND_TRUTH.get(key)
    if not fname:
        raise HTTPException(404, f"drawing {key} not found")
    path = GROUND_TRUTH / fname
    if not path.exists():
        raise HTTPException(404, f"ground truth missing for {key}")
    gt = json.loads(path.read_text())
    canvas = gt.get("canvas_size") or {"width": 0, "height": 0}
    equipment = [
        {"tag": e["tag"], "type": e.get("type"), "service": e.get("service"),
         "bbox": e.get("bbox")}
        for e in gt.get("equipment", []) if e.get("bbox")
    ]
    instruments = [
        {"tag": i["tag"], "function": i.get("function"),
         "located_on": i.get("located_on"), "bbox": i.get("bbox")}
        for i in gt.get("instruments", []) if i.get("bbox")
    ]
    lines = [
        {"line_no": l.get("line_no"), "size": l.get("size"),
         "service": l.get("service"), "spec": l.get("spec"),
         "from_tag": l.get("from_tag"), "to_tag": l.get("to_tag"),
         "geometry": l.get("geometry")}
        for l in gt.get("lines", [])
    ]
    return {
        "drawing_id": key,
        "source": "ground_truth",
        "canvas": canvas,
        "equipment": equipment,
        "instruments": instruments,
        "lines": lines,
    }


@app.get("/api/drawings/{key}/image")
def get_image(key: str, dpi: int = 150) -> Response:
    """Render the drawing image.

    Resolves three drawing-id shapes:
      1. demo keys in `DRAWING_PDFS` → `data/samples/<file>.pdf`
      2. ephemeral upload keys `upl-<hex>` → file under `/tmp/pnid_uploads/`
    """
    # Image-first: route every input through `normalize_to_png` so the
    # viewer's bytes are bit-identical to the orchestrator's analysis
    # input. Avoids the "viewer at scale X, agent at scale X+epsilon"
    # mismatch that left bbox overlays a pixel off.
    from backend.tools.image_normalize import normalize_to_png

    if key.startswith("upl-"):
        entry = get_registry().get(key)
        if not entry:
            raise HTTPException(404, f"upload {key} expired or not found")
        png_path = normalize_to_png(entry.path, dpi=dpi)
    else:
        pdf_name = DRAWING_PDFS.get(key)
        if not pdf_name:
            raise HTTPException(404, f"drawing {key} not found")
        pdf_path = (SAMPLES_REAL if is_real_sample(key) else SAMPLES) / pdf_name
        png_path = normalize_to_png(pdf_path, dpi=dpi)
    return Response(
        content=png_path.read_bytes(),
        media_type="image/png",
    )


class IndexRunRequest(BaseModel):
    drawing_id: str
    extraction: dict


@app.post("/api/index_run")
def index_run(req: IndexRunRequest) -> dict:
    """Index a freshly-completed live extraction into the SearchIndex
    so /api/query can answer questions about it.

    The frontend calls this once a Run finishes (live or replay). When
    the drawing_id matches an already-indexed entry, the new docs
    replace the old ones (re-add with same drawing_id).
    """
    from backend.agents.orchestrator import PipelineResult  # noqa: F401
    from backend.schemas import (
        ExtractionResult, from_dict_connection, from_dict_equipment,
        from_dict_instrument, from_dict_line,
    )
    from backend.tools.document_builder import build_docs

    ex = req.extraction
    extraction = ExtractionResult(
        drawing_id=req.drawing_id,
        drawing_type=ex.get("drawing_type", "P&ID"),
        title=ex.get("title"),
        drawing_no=ex.get("drawing_no"),
        equipment=tuple(from_dict_equipment(e) for e in ex.get("equipment", [])),
        instruments=tuple(from_dict_instrument(i) for i in ex.get("instruments", [])),
        lines=tuple(from_dict_line(l) for l in ex.get("lines", [])),
        connections=tuple(from_dict_connection(c) for c in ex.get("connections", [])),
    )
    s = state()
    s.ensure_index()
    docs = build_docs(extraction)
    s.index.add(docs, replace_drawing=True)
    return {
        "drawing_id": req.drawing_id,
        "indexed_docs": len(docs),
    }


@app.post("/api/uploads")
async def upload_drawing(file: UploadFile = File(...)) -> dict:
    """Accept a P&ID upload (PDF / PNG / JPG / TIFF, ≤10 MB).

    Returns the ephemeral drawing_id the SPA will use for the
    `/image` GET and the `ws_extract` WebSocket. Files live in the
    process-local upload registry and TTL out after 30 minutes.
    """
    payload = await file.read()
    try:
        entry = get_registry().register(payload)
    except UploadTooLarge:
        raise HTTPException(413, "file exceeds 10 MB")
    except UnsupportedUploadType:
        raise HTTPException(
            415,
            "only PDF, PNG, JPG, and TIFF uploads are supported",
        )
    return {
        "drawing_id": entry.drawing_id,
        "ext": entry.ext,
        "expires_at": entry.expires_at,
    }


class SearchRequest(BaseModel):
    query: str
    top_k: int = 6
    kind_filter: str | None = None
    drawing_filter: str | None = None


@app.post("/api/search")
def search(req: SearchRequest) -> dict:
    state().ensure_index()
    hits = state().index.search(
        req.query, top_k=req.top_k,
        kind_filter=req.kind_filter, drawing_filter=req.drawing_filter,
    )
    return {
        "query": req.query,
        "hits": [
            {"drawing_id": h.doc.drawing_id, "kind": h.doc.kind, "tag": h.doc.tag,
             "score": round(h.score, 4), "text": h.doc.text}
            for h in hits
        ],
    }


class SummaryRequest(BaseModel):
    drawing_id: str
    title: str | None = None
    extraction: dict
    verdict: str
    iterations_used: int = 0
    anomalies: list[dict] = []


@app.post("/api/summary")
def post_summary(req: SummaryRequest) -> dict:
    """Generate a Korean natural-language summary of a finished run.

    Called by the SPA at the end of every Run Live (or replay) so the
    audience reads "이 P&ID는 ..." instead of squinting at the counts
    row. Also reports which storage paths the result was written to,
    so the demo can surface a "SearchIndex 인덱싱 완료 / AgentCore
    Memory 저장 완료" toast.

    Sonnet 4.6 single-shot. The agent grounds strictly on the JSON
    we hand it (no retrieval).
    """
    from backend.agents.strands_summary import summarize
    from backend.schemas import (
        ExtractionResult, from_dict_connection, from_dict_equipment,
        from_dict_instrument, from_dict_line,
    )

    ex = req.extraction
    extraction = ExtractionResult(
        drawing_id=req.drawing_id,
        drawing_type="P&ID",
        title=req.title,
        drawing_no=None,
        equipment=tuple(from_dict_equipment(e) for e in ex.get("equipment", [])),
        instruments=tuple(from_dict_instrument(i) for i in ex.get("instruments", [])),
        lines=tuple(from_dict_line(l) for l in ex.get("lines", [])),
        connections=tuple(from_dict_connection(c) for c in ex.get("connections", [])),
    )
    memory_backend = (
        "agentcore" if os.getenv("BEDROCK_AGENTCORE_MEMORY_ID") else "in-memory"
    )
    summary_arn = os.getenv("AGENTCORE_SUMMARY_ARN")
    out: dict | None = None
    if summary_arn:
        # Route to the dedicated `pnidsummary` AgentCore Runtime first.
        # invoke_agent_runtime requires runtimeSessionId of length 33+,
        # so we use a UUID rather than the short drawing_id.
        try:
            import uuid
            client = boto3.client(
                "bedrock-agentcore",
                region_name=os.getenv("AWS_REGION", "us-east-1"),
            )
            payload = {
                "drawing_id": req.drawing_id,
                "title": req.title,
                "extraction": req.extraction,
                "verdict": req.verdict,
                "iterations_used": req.iterations_used,
                "anomalies": req.anomalies,
                "memory_backend": memory_backend,
            }
            resp = client.invoke_agent_runtime(
                agentRuntimeArn=summary_arn,
                runtimeSessionId=f"pnid-sum-{req.drawing_id}-{uuid.uuid4().hex}",
                payload=json.dumps(payload).encode("utf-8"),
            )
            body = resp["payload"].read()
            out = json.loads(body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            # Log so we can tell apart "fallback worked" from "hidden bug".
            print(f"[summary] runtime path failed, falling back: {exc!r}")
            out = None

    if out is None:
        # In-process Strands path (used when no ARN, or when the runtime
        # path threw above). Wrap in its own try so a parsing error in
        # the agent's reply doesn't blow up the request — we surface a
        # short failure message instead.
        try:
            out = summarize(
                drawing_id=req.drawing_id,
                title=req.title,
                extraction=extraction,
                verdict=req.verdict,
                iterations_used=req.iterations_used,
                anomalies=req.anomalies,
                memory_backend=memory_backend,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[summary] in-process path failed: {exc!r}")
            out = {
                "summary": (
                    f"요약 에이전트 호출에 실패했습니다 ({type(exc).__name__}). "
                    "추출 결과는 정상적으로 인덱싱되었으니 자연어 질의를 사용해 보세요."
                ),
                "suggested_queries": [],
            }
    return {
        "drawing_id": req.drawing_id,
        "summary": out.get("summary", ""),
        "suggested_queries": out.get("suggested_queries", []),
        "storage": {
            "search_index": "BM25 + Cohere Embed v4 (1536-d)",
            "memory_backend": memory_backend,
        },
    }


class QueryRequest(BaseModel):
    query: str
    top_k: int = 6
    drawing_filter: str | None = None  # restrict retrieval to one drawing_id


@app.post("/api/query")
def nl_query(req: QueryRequest) -> dict:
    """Natural-language query.

    Routing order (preview → stable → fallback):
      1. AgentCore Harness (declarative agent loop, preview) — used
         when AGENTCORE_HARNESS_ARN is set AND the boto3 SDK exposes
         `invoke_harness`. Today this is detected at runtime; the
         demo image still ships with botocore < the preview release,
         so the adapter quietly drops to step 2.
      2. AgentCore Runtime (managed Strands NL-query agent) — used
         when BEDROCK_AGENTCORE_RUNTIME_ARN is set. Production path
         today; data flow ECS → AgentCore Runtime → Bedrock.
      3. In-process Strands NL-query agent — local/dev/pytest only.
    """
    if os.getenv("AGENTCORE_HARNESS_ARN"):
        try:
            harness = get_default_harness_client()
            hr = harness.invoke(req.query, top_k=req.top_k)
            return {
                "query": req.query,
                "answer": hr.answer,
                "sources": hr.raw.get("sources", []),
                "backend": hr.backend,
            }
        except Exception:  # noqa: BLE001 — fall through to runtime/in-proc
            pass

    runtime = _agentcore()
    if runtime is not None:
        result = runtime.invoke({
            "action": "query",
            "query": req.query,
            "top_k": req.top_k,
            "drawing_filter": req.drawing_filter,
        })
        return result.payload

    state().ensure_index()
    a = answer(
        req.query, state().index, top_k=req.top_k,
        drawing_filter=req.drawing_filter,
    )
    # If filtering to the current drawing returned nothing (e.g. the
    # drawing was just live-extracted but never cached → not in the
    # SearchIndex), fall back to a global search so the user still
    # gets an answer instead of a dry "Not found".
    if not a.hits and req.drawing_filter:
        a = answer(req.query, state().index, top_k=req.top_k, drawing_filter=None)
    return {
        "query": req.query,
        "answer": a.text,
        "sources": [
            {"drawing_id": h.doc.drawing_id, "kind": h.doc.kind,
             "tag": h.doc.tag, "score": round(h.score, 4)}
            for h in a.hits
        ],
    }


@app.get("/api/memory/{session_id}")
def memory_list(session_id: str, actor_id: str = _DEFAULT_ACTOR) -> dict:
    items = _memory().list_drawings(actor_id, session_id)
    return {
        "actor_id": actor_id,
        "session_id": session_id,
        "count": len(items),
        "drawings": [
            {"drawing_id": m.drawing_id,
             "saved_at_s": m.saved_at_s,
             "summary": _memory_summary(m.payload)}
            for m in items
        ],
    }


@app.get("/api/memory/{session_id}/{drawing}")
def memory_recall(session_id: str, drawing: str, actor_id: str = _DEFAULT_ACTOR) -> dict:
    mem = _memory().get_drawing(actor_id, session_id, drawing)
    if mem is None:
        raise HTTPException(404, f"drawing {drawing} not found in session {session_id}")
    return {
        "actor_id": actor_id,
        "session_id": session_id,
        "drawing_id": mem.drawing_id,
        "saved_at_s": mem.saved_at_s,
        "summary": _memory_summary(mem.payload),
        "payload": mem.payload,
    }


def _resolve_input_path(key: str) -> Optional[Path]:
    """Resolve a drawing key to a local file path.

    Returns None when the key is unknown or expired. Used by both
    `ws_extract` and any future synchronous extract route.
    """
    if key.startswith("upl-"):
        entry = get_registry().get(key)
        return entry.path if entry else None
    pdf_name = DRAWING_PDFS.get(key)
    if not pdf_name:
        return None
    base = SAMPLES_REAL if is_real_sample(key) else SAMPLES
    return base / pdf_name


def _persist_pipeline_cache(key: str, payload: dict) -> None:
    """Write `payload` to the strands_pipeline cache file for `key`.

    Only pre-staged drawings persist; hero drawings already have a
    static cache and uploads are intentionally one-shot.
    """
    if key not in PRESTAGED_KEYS:
        return
    cache_dir = ROOT_FOR_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{key}_strands_pipeline.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


@app.websocket("/api/ws/extract/{key}")
async def ws_extract(websocket: WebSocket, key: str) -> None:
    """Stream live Strands pipeline progress events for `key`.

    Resolves `key` against `DRAWING_PDFS` (hero + pre-staged) or the
    upload registry (`upl-*`). After a successful run on a pre-staged
    drawing, the result is persisted to the strands_pipeline cache so
    the next click on that drawing falls back to the fast cached
    replay path.
    """
    input_path = _resolve_input_path(key)
    if input_path is None or not input_path.exists():
        await websocket.close(code=4404)
        return

    session_id = websocket.query_params.get("session_id", "default")
    actor_id = websocket.query_params.get("actor_id", _DEFAULT_ACTOR)

    await websocket.accept()
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[dict] = asyncio.Queue()
    DONE = object()

    def on_progress(evt: ProgressEvent) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {
                "type": "progress",
                "stage": evt.stage,
                "detail": evt.detail,
                "elapsed_s": evt.elapsed_s,
                "extra": evt.extra,
            },
        )

    def run() -> None:
        try:
            result = run_pipeline(input_path, drawing_id=key, on_progress=on_progress)
            payload = _result_to_payload(result)
            try:
                _memory().save_drawing(actor_id, session_id, key, payload)
            except Exception as exc:  # noqa: BLE001
                print(f"[ws_extract] memory save failed: {exc!r}")
            try:
                _persist_pipeline_cache(key, payload)
            except Exception as exc:  # noqa: BLE001
                print(f"[ws_extract] cache persist failed: {exc!r}")
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "result", **payload},
            )
        except Exception as e:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, DONE)

    loop.run_in_executor(None, run)

    try:
        while True:
            item = await queue.get()
            if item is DONE:
                break
            await websocket.send_text(json.dumps(item))
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
