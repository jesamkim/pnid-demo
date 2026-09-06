"""AgentCore Runtime entrypoint — Summary agent.

Invocation payload:
    {
      "drawing_id": "00",
      "title": "...",
      "extraction": {...ExtractionResult JSON...},
      "verdict": "needs_correction" | "pass",
      "iterations_used": 0,
      "anomalies": [...],
      "memory_backend": "agentcore" | "in-memory"
    }

Returns:
    {
      "summary": "한국어 4~6 문장 단락",
      "suggested_queries": [{"label": "...", "text": "..."}, ...]
    }
"""
from __future__ import annotations

from bedrock_agentcore import BedrockAgentCoreApp

from backend.agents.strands_summary import summarize
from backend.schemas import (
    ExtractionResult,
    from_dict_connection,
    from_dict_equipment,
    from_dict_instrument,
    from_dict_line,
)


app = BedrockAgentCoreApp(debug=False)


@app.entrypoint
def invoke(payload: dict) -> dict:
    ex = payload.get("extraction") or {}
    drawing_id = payload.get("drawing_id", "unknown")
    extraction = ExtractionResult(
        drawing_id=drawing_id,
        drawing_type=ex.get("drawing_type", "P&ID"),
        title=payload.get("title"),
        drawing_no=ex.get("drawing_no"),
        equipment=tuple(from_dict_equipment(x) for x in ex.get("equipment", [])),
        instruments=tuple(from_dict_instrument(x) for x in ex.get("instruments", [])),
        lines=tuple(from_dict_line(x) for x in ex.get("lines", [])),
        connections=tuple(from_dict_connection(x) for x in ex.get("connections", [])),
    )
    return summarize(
        drawing_id=drawing_id,
        title=payload.get("title"),
        extraction=extraction,
        verdict=str(payload.get("verdict", "")),
        iterations_used=int(payload.get("iterations_used", 0) or 0),
        anomalies=list(payload.get("anomalies") or []),
        memory_backend=str(payload.get("memory_backend", "in-memory")),
    )


if __name__ == "__main__":
    app.run()
