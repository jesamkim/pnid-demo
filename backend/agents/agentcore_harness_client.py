"""Adapter for the AgentCore Harness preview API.

AgentCore Harness (preview, 2026Q2) is the managed declarative agent loop:
the caller declares model + system prompt + tools inline and gets a
streaming response — no orchestration code, no container build, no
deploy step. The harness loop is implemented on top of Strands Agents.

Why this lives behind a thin adapter:

  - Harness is in **public preview** and the boto3 surface
    (`invoke_harness`, `create_harness`, …) is not yet exposed in the
    botocore release pinned by this image (1.42.69). The AWS docs at
    https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-get-started.html
    document the call shape, but the wire is not callable from a
    stock SDK install today.
  - Rather than ship dead-code or hand-roll the SigV4 streaming
    request, we feature-detect: when boto3 grows the operation we
    transparently swap to it; until then we fall back to the existing
    AgentCore *Runtime* path (`agentcore_runtime_client.py`) which
    already runs the same NL-query Strands agent in a managed microVM.

Public contract:

    HarnessClient.invoke(query, *, top_k=6, session_id=...) -> dict

    The return shape mirrors what `nl_query.answer(...)` would have
    produced inside the runtime, so `/api/query` doesn't need to know
    which path served the request.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Optional

import boto3


class HarnessNotConfigured(RuntimeError):
    """Raised when neither AGENTCORE_HARNESS_ARN nor a fallback runtime
    is wired."""


@dataclass(frozen=True)
class HarnessResult:
    answer: str
    raw: dict
    session_id: str
    backend: str  # "harness" | "runtime"


def _harness_available(client) -> bool:
    """boto3 SDK feature detection.

    Returns True only if the data-plane client exposes the
    `invoke_harness` operation. This is preview-gated; once GA the
    method appears in stock botocore and this returns True without
    any code change here.
    """
    return hasattr(client, "invoke_harness")


class HarnessClient:
    """Routes NL queries through Harness when available, else through
    AgentCore Runtime."""

    def __init__(
        self,
        *,
        harness_arn: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> None:
        self._harness_arn = harness_arn or os.getenv("AGENTCORE_HARNESS_ARN")
        self._region = region_name or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-agentcore", region_name=self._region)

    def invoke(
        self,
        query: str,
        *,
        top_k: int = 6,
        session_id: Optional[str] = None,
    ) -> HarnessResult:
        sid = session_id or _new_session_id()
        if self._harness_arn and _harness_available(self._client):
            return self._invoke_harness(query, top_k=top_k, session_id=sid)
        return self._invoke_runtime_fallback(query, top_k=top_k, session_id=sid)

    def _invoke_harness(
        self, query: str, *, top_k: int, session_id: str
    ) -> HarnessResult:
        # invoke_harness is documented at
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-get-started.html
        # Streaming event shape: messageStart / contentBlockDelta / messageStop.
        response = self._client.invoke_harness(
            harnessArn=self._harness_arn,
            runtimeSessionId=session_id,
            messages=[{
                "role": "user",
                "content": [{"text": _format_prompt(query, top_k=top_k)}],
            }],
        )
        text_chunks: list[str] = []
        for event in response["stream"]:
            delta = event.get("contentBlockDelta", {}).get("delta", {})
            if "text" in delta:
                text_chunks.append(delta["text"])
            if "runtimeClientError" in event:
                raise RuntimeError(event["runtimeClientError"]["message"])
        answer = "".join(text_chunks).strip()
        return HarnessResult(
            answer=answer,
            raw={"answer": answer, "sources": []},
            session_id=session_id,
            backend="harness",
        )

    def _invoke_runtime_fallback(
        self, query: str, *, top_k: int, session_id: str
    ) -> HarnessResult:
        from .agentcore_runtime_client import AgentCoreRuntimeClient
        runtime = AgentCoreRuntimeClient()
        result = runtime.invoke(
            {"action": "query", "query": query, "top_k": top_k},
            session_id=session_id,
        )
        return HarnessResult(
            answer=str(result.payload.get("answer", "")),
            raw=result.payload,
            session_id=session_id,
            backend="runtime",
        )


def _format_prompt(query: str, *, top_k: int) -> str:
    """Match the system prompt used by the in-process NL agent so the
    harness loop produces grounded answers over the same indexed
    drawings."""
    return (
        "You are a P&ID inspection assistant grounded only in the "
        "indexed drawings the orchestrator provides via the search tool. "
        f"Use the top {top_k} hits and cite tag IDs. "
        "Answer in the user's language (English or Korean).\n\n"
        f"Question: {query}"
    )


def _new_session_id() -> str:
    """invoke_harness requires runtimeSessionId >= 33 chars."""
    return f"pnid-demo-{uuid.uuid4().hex}"


_DEFAULT: Optional[HarnessClient] = None


def get_default_harness_client() -> HarnessClient:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = HarnessClient()
    return _DEFAULT


def reset_default_harness_client() -> None:
    global _DEFAULT
    _DEFAULT = None
