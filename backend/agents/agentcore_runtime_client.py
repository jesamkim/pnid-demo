"""Client for invoking the demo's AgentCore Runtime deployment.

`agent_main.py` is deployed as an AgentCore Runtime artifact via the
starter-toolkit (`agentcore deploy`). The ECS-hosted FastAPI backend
calls into that runtime through this client so the production data
flow is `Browser -> CloudFront -> ALB -> ECS -> AgentCore Runtime ->
Bedrock`, matching the architecture the user expects.

Behavior:
  - When `BEDROCK_AGENTCORE_RUNTIME_ARN` is set, the client calls
    `bedrock-agentcore.invoke_agent_runtime` with the same payload
    shape used in tests and the local SDK.
  - When the env var is missing, `invoke()` raises so callers can
    fall back to the in-process Strands path (kept for offline/local
    development and pytest).

Streaming: `invoke_agent_runtime` returns a streaming response body
(`payload`) which we drain into one JSON document. WebSocket-style
progress streaming is handled by the in-process orchestrator (which
remains available); the AgentCore client is for atomic JSON RPC-style
calls (query / recall / list_session / extract).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import boto3


class AgentCoreRuntimeNotConfigured(RuntimeError):
    """Raised when no `BEDROCK_AGENTCORE_RUNTIME_ARN` is set."""


@dataclass(frozen=True)
class InvocationResult:
    payload: dict
    session_id: str


class AgentCoreRuntimeClient:
    """Thin wrapper around boto3's `bedrock-agentcore` client."""

    def __init__(
        self,
        *,
        runtime_arn: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> None:
        self._runtime_arn = runtime_arn or os.getenv(
            "BEDROCK_AGENTCORE_RUNTIME_ARN"
        )
        if not self._runtime_arn:
            raise AgentCoreRuntimeNotConfigured(
                "Set BEDROCK_AGENTCORE_RUNTIME_ARN to invoke the deployed "
                "agent. Without it, callers should use the in-process "
                "Strands path (e.g. backend.agents.strands_orchestrator)."
            )
        self._client = boto3.client(
            "bedrock-agentcore",
            region_name=region_name or os.getenv("AWS_REGION", "us-east-1"),
        )

    def invoke(self, payload: dict, *, session_id: str = "default") -> InvocationResult:
        """Invoke the deployed agent runtime with the given JSON payload.

        Raises on transport failure; the agent's own `{"error": "..."}`
        responses are returned verbatim so the caller can decide how to
        surface them.
        """
        response = self._client.invoke_agent_runtime(
            agentRuntimeArn=self._runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8"),
        )
        body = response["payload"].read()
        try:
            decoded = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"AgentCore Runtime returned non-JSON payload: {body!r}"
            ) from exc
        return InvocationResult(payload=decoded, session_id=session_id)


_DEFAULT: Optional[AgentCoreRuntimeClient] = None


def get_default_client() -> AgentCoreRuntimeClient:
    """Lazily-built singleton. Raises `AgentCoreRuntimeNotConfigured`
    when the env var is missing — callers should catch that and fall
    back to in-process Strands."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AgentCoreRuntimeClient()
    return _DEFAULT


def reset_default_client() -> None:
    global _DEFAULT
    _DEFAULT = None
