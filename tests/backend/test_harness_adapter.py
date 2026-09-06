"""Harness adapter routing tests.

Covers feature-detect of `invoke_harness` (preview-gated) and the
runtime fallback so /api/query keeps a stable contract regardless of
which AgentCore surface is wired up.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.agentcore_harness_client import (
    HarnessClient,
    _harness_available,
    _new_session_id,
    reset_default_harness_client,
)


def test_session_id_is_long_enough_for_invoke_harness():
    sid = _new_session_id()
    assert len(sid) >= 33


def test_feature_detect_returns_false_when_method_absent():
    fake = MagicMock(spec=[])  # no methods
    assert _harness_available(fake) is False


def test_feature_detect_returns_true_when_method_present():
    fake = MagicMock()
    fake.invoke_harness = MagicMock()
    assert _harness_available(fake) is True


def test_invoke_falls_back_to_runtime_when_harness_arn_unset(monkeypatch):
    monkeypatch.delenv("AGENTCORE_HARNESS_ARN", raising=False)
    reset_default_harness_client()

    runtime_stub = MagicMock()
    runtime_stub.invoke.return_value = MagicMock(
        payload={"answer": "PSV-101", "sources": [{"tag": "PSV-101"}]},
        session_id="sess-1",
    )

    with patch(
        "backend.agents.agentcore_runtime_client.AgentCoreRuntimeClient",
        return_value=runtime_stub,
    ):
        client = HarnessClient(harness_arn=None, region_name="us-east-1")
        result = client.invoke("V-101 PSV?", top_k=4)

    assert result.backend == "runtime"
    assert result.answer == "PSV-101"
    runtime_stub.invoke.assert_called_once()
    args, kwargs = runtime_stub.invoke.call_args
    assert args[0] == {"action": "query", "query": "V-101 PSV?", "top_k": 4}


def test_invoke_uses_harness_when_arn_set_and_sdk_supports(monkeypatch):
    monkeypatch.setenv("AGENTCORE_HARNESS_ARN", "arn:aws:...:harness/X")
    reset_default_harness_client()

    fake_event_stream = [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockDelta": {"delta": {"text": "PSV-101 protects "}}},
        {"contentBlockDelta": {"delta": {"text": "V-101."}}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]

    fake_client: Any = MagicMock()
    fake_client.invoke_harness = MagicMock(
        return_value={"stream": iter(fake_event_stream)},
    )

    with patch(
        "backend.agents.agentcore_harness_client.boto3.client",
        return_value=fake_client,
    ):
        client = HarnessClient(
            harness_arn="arn:aws:...:harness/X", region_name="us-east-1",
        )
        result = client.invoke("V-101 PSV?", top_k=4)

    assert result.backend == "harness"
    assert result.answer == "PSV-101 protects V-101."
    fake_client.invoke_harness.assert_called_once()
    call_kwargs = fake_client.invoke_harness.call_args.kwargs
    assert call_kwargs["harnessArn"] == "arn:aws:...:harness/X"
    assert len(call_kwargs["runtimeSessionId"]) >= 33
    assert call_kwargs["messages"][0]["role"] == "user"


def test_invoke_propagates_runtime_client_error(monkeypatch):
    monkeypatch.setenv("AGENTCORE_HARNESS_ARN", "arn:aws:...:harness/X")

    fake_event_stream = [
        {"messageStart": {"role": "assistant"}},
        {"runtimeClientError": {"message": "tool execution failed"}},
    ]
    fake_client: Any = MagicMock()
    fake_client.invoke_harness = MagicMock(
        return_value={"stream": iter(fake_event_stream)},
    )

    with patch(
        "backend.agents.agentcore_harness_client.boto3.client",
        return_value=fake_client,
    ):
        client = HarnessClient(
            harness_arn="arn:aws:...:harness/X", region_name="us-east-1",
        )
        with pytest.raises(RuntimeError, match="tool execution failed"):
            client.invoke("V-101 PSV?", top_k=4)
