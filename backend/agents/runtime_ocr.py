"""AgentCore Runtime entrypoint — OCR agent (Textract wrapper).

Invocation payload:
    {"image_b64": "<base64 PNG>"}

Returns the list of TextBlock dicts (text, confidence, bbox).
"""
from __future__ import annotations

import base64
import io
from dataclasses import asdict

from PIL import Image
from bedrock_agentcore import BedrockAgentCoreApp

from backend.agents.strands_ocr import detect_text_blocks


app = BedrockAgentCoreApp(debug=False)


@app.entrypoint
def invoke(payload: dict) -> dict:
    image_b64 = payload.get("image_b64")
    if not image_b64:
        return {"error": "missing image_b64"}
    img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
    blocks = detect_text_blocks(img)
    return {
        "blocks": [
            {"text": b.text, "confidence": b.confidence, "bbox": list(b.bbox)}
            for b in blocks
        ],
    }


if __name__ == "__main__":
    app.run()
