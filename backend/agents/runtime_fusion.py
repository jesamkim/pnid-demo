"""AgentCore Runtime entrypoint — Fusion agent.

Invocation payload:
    {
      "vision_extraction": {ExtractionResult JSON},
      "ocr_blocks": [{"text": ..., "confidence": ..., "bbox": [...] }],
      "canvas": [width, height]
    }

Returns the upgraded ExtractionResult JSON + per-tag fusion events.
"""
from __future__ import annotations

from dataclasses import asdict

from bedrock_agentcore import BedrockAgentCoreApp

from backend.agents.strands_fusion import fuse
from backend.agents.strands_ocr import TextBlock
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
    raw = payload.get("vision_extraction") or {}
    vision = ExtractionResult(
        drawing_id=raw.get("drawing_id", "unknown"),
        drawing_type=raw.get("drawing_type", "P&ID"),
        title=raw.get("title"),
        drawing_no=raw.get("drawing_no"),
        equipment=tuple(from_dict_equipment(x) for x in raw.get("equipment", [])),
        instruments=tuple(from_dict_instrument(x) for x in raw.get("instruments", [])),
        lines=tuple(from_dict_line(x) for x in raw.get("lines", [])),
        connections=tuple(from_dict_connection(x) for x in raw.get("connections", [])),
    )
    ocr_blocks = tuple(
        TextBlock(text=b["text"], confidence=float(b["confidence"]),
                   bbox=tuple(b["bbox"]))
        for b in payload.get("ocr_blocks", [])
    )
    canvas = tuple(payload.get("canvas") or (0, 0))
    result = fuse(vision, ocr_blocks, canvas=canvas if canvas[0] else None)
    return {
        "extraction": {
            "drawing_id": result.extraction.drawing_id,
            "equipment": [asdict(e) for e in result.extraction.equipment],
            "instruments": [asdict(i) for i in result.extraction.instruments],
            "lines": [asdict(l) for l in result.extraction.lines],
            "connections": [asdict(c) for c in result.extraction.connections],
        },
        "events": list(result.events),
        "matched": {
            "equipment": result.matched_equipment,
            "instruments": result.matched_instruments,
            "lines": result.matched_lines,
        },
    }


if __name__ == "__main__":
    app.run()
