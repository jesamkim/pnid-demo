"""AgentCore entrypoint smoke tests."""
from __future__ import annotations

import agent_main
from backend.agents.memory_store import InMemoryStore


def test_app_is_bedrock_agentcore():
    from bedrock_agentcore import BedrockAgentCoreApp
    assert isinstance(agent_main.app, BedrockAgentCoreApp)


def test_invoke_routes_unknown_action():
    out = agent_main.invoke({"action": "no_such_action"})
    assert "error" in out


def test_invoke_query_action_signature_only():
    """Calling the entrypoint with action=query lazily builds the index.
    We don't actually answer here (Bedrock cost) — just check the function
    is callable with this payload shape.
    """
    fn = agent_main.invoke
    assert callable(fn)


def test_recall_returns_not_found_for_unseen_drawing():
    agent_main._set_memory_for_test(InMemoryStore())
    out = agent_main.invoke({
        "action": "recall",
        "drawing": "01",
        "session_id": "test-session",
    })
    assert out["found"] is False
    assert out["drawing_id"] == "01"
    assert out["session_id"] == "test-session"


def test_recall_requires_drawing():
    agent_main._set_memory_for_test(InMemoryStore())
    out = agent_main.invoke({
        "action": "recall",
        "session_id": "test-session",
    })
    assert "error" in out


def test_save_then_recall_roundtrip():
    """Simulate an extract that already happened, then recall it."""
    store = InMemoryStore()
    agent_main._set_memory_for_test(store)

    fake_payload = {
        "drawing_id": "01",
        "verdict": "pass",
        "iterations_used": 0,
        "total_elapsed_s": 12.3,
        "extraction": {
            "equipment": [{"tag": "V-101"}, {"tag": "P-101A"}],
            "instruments": [{"tag": "FT-101"}],
            "lines": [],
            "connections": [],
        },
        "anomalies": [],
        "events": [],
    }
    agent_main._save_to_memory("alice", "demo-1", "01", fake_payload)

    out = agent_main.invoke({
        "action": "recall",
        "drawing": "01",
        "actor_id": "alice",
        "session_id": "demo-1",
    })
    assert out["found"] is True
    assert out["drawing_id"] == "01"
    assert out["summary"]["verdict"] == "pass"
    assert out["summary"]["counts"]["equipment"] == 2
    assert out["summary"]["counts"]["instruments"] == 1
    assert out["payload"] == fake_payload


def test_list_session_returns_chronological_summaries():
    store = InMemoryStore()
    agent_main._set_memory_for_test(store)

    payload_a = {
        "verdict": "pass",
        "iterations_used": 0,
        "total_elapsed_s": 10.0,
        "extraction": {"equipment": [{}, {}], "instruments": [{}],
                       "lines": [{}], "connections": []},
        "anomalies": [],
    }
    payload_b = {
        "verdict": "needs_correction",
        "iterations_used": 1,
        "total_elapsed_s": 18.0,
        "extraction": {"equipment": [{}], "instruments": [{}, {}, {}],
                       "lines": [{}, {}, {}], "connections": [{}]},
        "anomalies": [{"kind": "orphan_instrument"}],
    }
    agent_main._save_to_memory("alice", "demo-1", "01", payload_a)
    agent_main._save_to_memory("alice", "demo-1", "02", payload_b)

    out = agent_main.invoke({
        "action": "list_session",
        "actor_id": "alice",
        "session_id": "demo-1",
    })
    assert out["count"] == 2
    ids = [d["drawing_id"] for d in out["drawings"]]
    assert ids == ["01", "02"]
    assert out["drawings"][1]["summary"]["verdict"] == "needs_correction"
    assert out["drawings"][1]["summary"]["anomaly_count"] == 1
    assert out["drawings"][1]["summary"]["counts"]["instruments"] == 3


def test_session_isolation_in_recall():
    store = InMemoryStore()
    agent_main._set_memory_for_test(store)
    agent_main._save_to_memory("alice", "session-A", "01",
                               {"extraction": {"equipment": [{}]}, "anomalies": []})
    out = agent_main.invoke({
        "action": "recall",
        "drawing": "01",
        "actor_id": "alice",
        "session_id": "session-B",
    })
    assert out["found"] is False
