"""AgentCore Runtime entrypoint — Valve Scanner agent.

Deploys via:
    agentcore configure -e backend/agents/runtime_valve.py -n pnidvalve
    agentcore deploy

Invocation payload:
    {
      "image_b64": "<base64 PNG crop>",
      "zone_topic": "KA002 column area",
      "known_equipment_tags": ["KA002", "BA100", ...]
    }

Returns a JSON array of detected valves (Equipment-shaped dicts).
"""
from __future__ import annotations

import base64
import io
import json
from dataclasses import asdict

from PIL import Image
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

from backend.strands_models import primary_model

app = BedrockAgentCoreApp(debug=False)

SYSTEM = """You are a valve symbol detector for engineering P&ID drawings.

You receive a cropped section of a P&ID. Your SOLE JOB is to find every
inline valve symbol that sits ON a process line within this crop.

Valve symbols to look for:
- Gate valve: small rectangle/bowtie shape straddling a line
- Ball valve: circle with a line through it
- Control valve: triangle-pair (bowtie) with a circle actuator on top
- Check valve: triangle pointing in flow direction
- Safety/relief valve: angled shape with spring symbol on top

For each valve found, output:
  tag: the alphanumeric label next to it (e.g. "AB014", "XV-101"), or
       "UNNAMED" if no label is visible
  type: "gate_valve" | "ball_valve" | "control_valve" | "check_valve" | "safety_valve"
  on_line: which line_no the valve sits on (if readable), else null
  bbox_norm: [left, top, right, bottom] in 0..1 relative to this crop

Return a JSON array. If no valves are found, return [].
Do NOT include items already listed in the known equipment below.
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
    zone_topic = payload.get("zone_topic", "unknown zone")
    known_tags = payload.get("known_equipment_tags", [])

    if not image_b64:
        return {"error": "missing image_b64", "valves": []}

    img = Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    agent = Agent(model=primary_model(), system_prompt=SYSTEM, callback_handler=None)
    user = (
        f"Zone: {zone_topic}\n"
        f"Known equipment (do NOT re-detect): {known_tags}\n\n"
        "Find all valve symbols in this crop."
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
    valves = []
    if start >= 0 and end > start:
        try:
            valves = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {"zone_topic": zone_topic, "valves": valves}


if __name__ == "__main__":
    app.run()
