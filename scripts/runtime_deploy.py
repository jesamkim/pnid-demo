"""Deploy three Strands-based agents to Bedrock AgentCore Runtime.

Uses the official `bedrock_agentcore_starter_toolkit.Runtime` Python
API in non-interactive mode. The agent code itself is *unchanged*
Strands SDK — this script just wraps build + push + create_agent_runtime
without an interactive shell.

Run:
    AWS_PROFILE=profile2 python3 scripts/runtime_deploy.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bedrock_agentcore_starter_toolkit import Runtime  # noqa: E402

REGION = os.environ.get("AWS_REGION", "us-east-1")
REQUIREMENTS = str(ROOT / "requirements.txt")

# Each agent is a thin Strands wrapper exposed via BedrockAgentCoreApp.
AGENTS = [
    {
        "name": "pnidvision",
        "entrypoint": "backend/agents/runtime_vision.py",
        "description": "Strands Vision agent (Opus 4.8) — extract equipment/instruments/lines",
    },
    {
        "name": "pnidocr",
        "entrypoint": "backend/agents/runtime_ocr.py",
        "description": "Strands OCR agent (Textract wrapper) — pixel-precise label bboxes",
    },
    {
        "name": "pnidfusion",
        "entrypoint": "backend/agents/runtime_fusion.py",
        "description": "Strands Fusion agent — match Vision tags to OCR coordinates",
    },
    {
        "name": "pnidsummary",
        "entrypoint": "backend/agents/runtime_summary.py",
        "description": "Strands Summary agent (Sonnet 4.6) — Korean NL summary + dynamic suggested queries",
    },
    {
        "name": "pnidvalve",
        "entrypoint": "backend/agents/runtime_valve.py",
        "description": "Strands Valve Scanner (Opus 4.8) — detects inline valves on process lines per zone crop",
    },
    {
        "name": "pnidstitch",
        "entrypoint": "backend/agents/runtime_stitch.py",
        "description": "Strands Connection Stitcher (Opus 4.8) — traces process lines to fill missing connections",
    },
]


def deploy_one(spec: dict) -> dict:
    runtime = Runtime()
    print(f"\n=== configuring {spec['name']} ===")
    cfg = runtime.configure(
        entrypoint=str(ROOT / spec["entrypoint"]),
        agent_name=spec["name"],
        requirements_file=REQUIREMENTS,
        region=REGION,
        # toolkit creates the ECR repo and execution role on first run.
        auto_create_ecr=True,
        auto_create_execution_role=True,
        non_interactive=True,
        deployment_type="container",
        disable_otel=False,
    )
    print(f"  configured: agent={spec['name']} ecr={getattr(cfg, 'ecr_repository', 'auto')}")

    print(f"=== launching {spec['name']} (build + push + create_agent_runtime)…")
    launched = runtime.launch()
    arn = getattr(launched, "agent_arn", None) or getattr(launched, "agentRuntimeArn", None)
    print(f"  done: ARN = {arn}")
    return {
        "name": spec["name"],
        "arn": arn,
        "configure": cfg.__dict__ if hasattr(cfg, "__dict__") else str(cfg),
        "launch": launched.__dict__ if hasattr(launched, "__dict__") else str(launched),
    }


def main() -> None:
    if not os.environ.get("AWS_PROFILE") and not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("WARN: no AWS credentials in env. Set AWS_PROFILE=profile2 first.")

    # Optional subset: `--only pnidvision,pnidvalve,pnidstitch` (or the
    # RUNTIME_ONLY env). Useful when a model change only touches the
    # Opus-backed agents and the Sonnet ones don't need a rebuild.
    only_arg = os.environ.get("RUNTIME_ONLY", "")
    if "--only" in sys.argv:
        only_arg = sys.argv[sys.argv.index("--only") + 1]
    only = {n.strip() for n in only_arg.split(",") if n.strip()}
    specs = [s for s in AGENTS if not only or s["name"] in only]
    print(f"deploying: {[s['name'] for s in specs]}")

    out: list[dict] = []
    for spec in specs:
        try:
            out.append(deploy_one(spec))
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {spec['name']} failed: {exc!r}")
            out.append({"name": spec["name"], "error": repr(exc)})
    log_path = ROOT / ".claude" / "logs" / "runtime_deploy.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {log_path}")
    print()
    print("Next: export the ARNs and redeploy the App stack:")
    env_names = {
        "pnidvision": "AGENTCORE_VISION_ARN",
        "pnidocr": "AGENTCORE_OCR_ARN",
        "pnidfusion": "AGENTCORE_FUSION_ARN",
        "pnidsummary": "AGENTCORE_SUMMARY_ARN",
        "pnidvalve": "AGENTCORE_VALVE_ARN",
        "pnidstitch": "AGENTCORE_STITCH_ARN",
    }
    for r in out:
        if r.get("arn"):
            env_name = env_names.get(r["name"], r["name"].upper() + "_ARN")
            print(f"  export {env_name}={r['arn']}")


if __name__ == "__main__":
    main()
