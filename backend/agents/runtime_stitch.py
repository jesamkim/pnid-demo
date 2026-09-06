"""AgentCore Runtime entrypoint — Connection Stitcher agent.

Deploys via:
    agentcore configure -e backend/agents/runtime_stitch.py -n pnidstitch
    agentcore deploy

Invocation payload:
    {
      "image_b64": "<base64 full-page PNG>",
      "extraction_json": { ... ExtractionResult-shaped dict ... }
    }

Returns a JSON array of NEW connections not already in the extraction.
"""
from __future__ import annotations

import base64
import io
import json

from PIL import Image
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

from backend.strands_models import primary_model

app = BedrockAgentCoreApp(debug=False)

SYSTEM = """You are a P&ID connection analyst. You receive:
1. An image of the complete P&ID drawing.
2. A JSON extraction listing all detected equipment, instruments, and lines.

Your job is to TRACE PROCESS LINES on the drawing and identify MISSING
connections. A connection links two items (equipment, instruments) via a
line or signal path.

Rules:
- Only report connections you can visually confirm by following a line on
  the drawing. Never guess or infer from naming conventions alone.
- For each new connection, specify:
    from_tag: the tag of the origin item
    to_tag: the tag of the destination item
    type: "process" (pipe), "signal" (instrument signal), or "utility"
    via_line: the line_no if one is visible, else null
- Do NOT duplicate connections already in the input JSON.
- Focus on:
  a) Equipment → Equipment process connections (following physical pipes)
  b) Instrument → Equipment signal connections (dotted/dashed lines)
  c) Filling null from_tag/to_tag on existing lines (report as a connection)
- Return ONLY a JSON array of new Connection objects. No preamble, no fences.
  Example: [{"from_tag": "KA002", "to_tag": "WA008", "type": "process", "via_line": "LR040.22040-80-40C1200 NF 223"}]
- If you find no new connections, return an empty array: []
"""


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


@app.entrypoint
def invoke(payload: dict) -> dict:
    image_b64 = payload.get("image_b64")
    extraction_json = payload.get("extraction_json", {})

    if not image_b64:
        return {"error": "missing image_b64", "new_connections": []}

    img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    summary = json.dumps(extraction_json, ensure_ascii=False)
    agent = Agent(model=primary_model(), system_prompt=SYSTEM, callback_handler=None)
    user = (
        f"Current extraction:\n{summary}\n\n"
        "Trace lines on this drawing and return NEW connections only."
    )
    message = [
        {"image": {"format": "png", "source": {"bytes": img_bytes}}},
        {"text": user},
    ]
    result = agent(message)
    raw = _agent_text(result).strip()

    import re
    text = raw
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    connections = []
    if start >= 0 and end > start:
        try:
            connections = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {"new_connections": connections}


if __name__ == "__main__":
    app.run()
