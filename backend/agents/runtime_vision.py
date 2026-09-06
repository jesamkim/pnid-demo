"""AgentCore Runtime entrypoint — Vision agent.

Deploys via:
    agentcore configure -e backend/agents/runtime_vision.py -n agent-vision
    agentcore deploy

Invocation payload:
    {"image_b64": "<base64 PNG>", "drawing_id": "..."}

Returns the ExtractionResult JSON shape.
"""
from __future__ import annotations

import base64
import io
from dataclasses import asdict

from PIL import Image
from bedrock_agentcore import BedrockAgentCoreApp

from backend.agents.strands_extractor import extract_from_image


app = BedrockAgentCoreApp(debug=False)


@app.entrypoint
def invoke(payload: dict) -> dict:
    image_b64 = payload.get("image_b64")
    drawing_id = payload.get("drawing_id", "unknown")
    if not image_b64:
        return {"error": "missing image_b64"}
    img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
    extraction, meta = extract_from_image(img, drawing_id=drawing_id)
    return {
        "drawing_id": drawing_id,
        "extraction": {
            "equipment": [asdict(e) for e in extraction.equipment],
            "instruments": [asdict(i) for i in extraction.instruments],
            "lines": [asdict(l) for l in extraction.lines],
            "connections": [asdict(c) for c in extraction.connections],
        },
        "meta": meta,
    }


if __name__ == "__main__":
    app.run()
