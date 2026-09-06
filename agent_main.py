"""AgentCore Runtime entry point for the P&ID Agentic pipeline.

Deploys via:
    agentcore configure -e agent_main.py -n pnid-agentic-demo
    agentcore deploy

Invocation payload:
    {"action": "extract", "drawing": "01"}
    {"action": "extract", "drawing": "01b"}
    {"action": "extract_path", "pdf_path": "s3://.../my.pdf", "drawing_id": "user-123"}
    {"action": "query", "query": "PSV protecting V-101?"}
    {"action": "recall", "drawing": "01", "session_id": "demo-1"}
    {"action": "list_session", "session_id": "demo-1"}

Cross-session memory:
    Set BEDROCK_AGENTCORE_MEMORY_ID to persist runs in AgentCore Memory.
    Without it, a process-local InMemoryStore is used (dev / smoke tests).
    actor_id / session_id are read from the payload, defaulting to
    "demo-presenter" / "default" so a single-presenter rehearsal works
    out of the box.

The Runtime auto-instruments OpenTelemetry traces (CloudWatch GenAI
Observability), so each agent step is visible in CloudWatch Logs and the
Bedrock GenAI dashboard without extra code.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from bedrock_agentcore import BedrockAgentCoreApp

from backend.agents.memory_store import (
    AgentCoreStore,
    DrawingMemory,
    MemoryStore,
    get_default_store,
)
from backend.agents.strands_nl_query import answer
from backend.agents.strands_orchestrator import run_pipeline
from backend.api.state import DRAWING_PDFS, SAMPLES, state
from backend.config import get_settings


app = BedrockAgentCoreApp(debug=False)

_DEFAULT_ACTOR = "demo-presenter"
_DEFAULT_SESSION = "default"

_MEMORY: Optional[MemoryStore] = None


def _memory() -> MemoryStore:
    global _MEMORY
    if _MEMORY is not None:
        return _MEMORY
    memory_id = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
    if memory_id:
        _MEMORY = AgentCoreStore(
            memory_id=memory_id,
            region_name=get_settings().aws_region,
        )
    else:
        _MEMORY = get_default_store()
    return _MEMORY


def _set_memory_for_test(store: MemoryStore) -> None:
    """Test hook — replaces the module-level memory backend."""
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
    """Lossy projection used when listing past runs in a session."""
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


def _ids(payload: dict) -> tuple[str, str]:
    actor = str(payload.get("actor_id") or _DEFAULT_ACTOR)
    session = str(payload.get("session_id") or _DEFAULT_SESSION)
    return actor, session


def _save_to_memory(actor: str, session: str, drawing_id: str, payload: dict) -> None:
    """Best-effort memory write. Never fails the user request on memory error."""
    try:
        _memory().save_drawing(actor, session, drawing_id, payload)
    except Exception as exc:  # noqa: BLE001
        # Surface in logs (CloudWatch when deployed) but don't break the response.
        print(f"[memory] save_drawing failed: {exc!r}")


@app.entrypoint
def invoke(payload: dict) -> dict:
    action = payload.get("action", "extract")
    actor, session = _ids(payload)

    if action == "extract":
        key = payload.get("drawing", "01")
        pdf = SAMPLES / DRAWING_PDFS.get(key, DRAWING_PDFS["01"])
        result = run_pipeline(pdf, drawing_id=key)
        out = _result_to_payload(result)
        _save_to_memory(actor, session, result.drawing_id, out)
        return out

    if action == "extract_path":
        pdf_path = Path(payload["pdf_path"])
        drawing_id = payload.get("drawing_id", pdf_path.stem)
        result = run_pipeline(pdf_path, drawing_id=drawing_id)
        out = _result_to_payload(result)
        _save_to_memory(actor, session, result.drawing_id, out)
        return out

    if action == "query":
        state().ensure_index()
        q = payload.get("query", "")
        a = answer(q, state().index, top_k=int(payload.get("top_k", 6)))
        return {
            "query": q,
            "answer": a.text,
            "sources": [
                {"drawing_id": h.doc.drawing_id, "kind": h.doc.kind,
                 "tag": h.doc.tag, "score": round(h.score, 4)}
                for h in a.hits
            ],
        }

    if action == "recall":
        drawing_id = payload.get("drawing")
        if not drawing_id:
            return {"error": "recall requires 'drawing'"}
        mem = _memory().get_drawing(actor, session, drawing_id)
        if mem is None:
            return {
                "found": False,
                "actor_id": actor,
                "session_id": session,
                "drawing_id": drawing_id,
            }
        return {
            "found": True,
            "actor_id": actor,
            "session_id": session,
            "drawing_id": mem.drawing_id,
            "saved_at_s": mem.saved_at_s,
            "summary": _memory_summary(mem.payload),
            "payload": mem.payload,
        }

    if action == "list_session":
        items: tuple[DrawingMemory, ...] = _memory().list_drawings(actor, session)
        return {
            "actor_id": actor,
            "session_id": session,
            "count": len(items),
            "drawings": [
                {
                    "drawing_id": m.drawing_id,
                    "saved_at_s": m.saved_at_s,
                    "summary": _memory_summary(m.payload),
                }
                for m in items
            ],
        }

    return {"error": f"unknown action: {action}"}


if __name__ == "__main__":
    app.run()
