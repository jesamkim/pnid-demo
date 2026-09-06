"""Tests for backend.agents.memory_store.

Covers the in-memory backend (no AWS), the AgentCoreStore decoder
(via a fake MemoryClient), and the singleton helper.
"""
from __future__ import annotations

import json
import time

import pytest

from backend.agents.memory_store import (
    AgentCoreStore,
    DrawingMemory,
    InMemoryStore,
    _event_to_memory,
    get_default_store,
    reset_default_store,
)


def _payload(eq_count: int = 8) -> dict:
    return {"verdict": "pass", "extraction": {"equipment_count": eq_count}}


def test_inmemory_save_and_get_roundtrip():
    store = InMemoryStore()
    saved = store.save_drawing("alice", "sess-1", "01", _payload())

    got = store.get_drawing("alice", "sess-1", "01")
    assert got is not None
    assert got.drawing_id == "01"
    assert got.payload == _payload()
    assert got.actor_id == "alice"
    assert got.session_id == "sess-1"
    assert got.saved_at_s == saved.saved_at_s


def test_inmemory_session_isolation():
    store = InMemoryStore()
    store.save_drawing("alice", "sess-1", "01", _payload(8))
    store.save_drawing("alice", "sess-2", "01", _payload(99))

    got_1 = store.get_drawing("alice", "sess-1", "01")
    got_2 = store.get_drawing("alice", "sess-2", "01")
    assert got_1 is not None and got_1.payload["extraction"]["equipment_count"] == 8
    assert got_2 is not None and got_2.payload["extraction"]["equipment_count"] == 99


def test_inmemory_actor_isolation():
    store = InMemoryStore()
    store.save_drawing("alice", "sess-x", "01", _payload(8))
    store.save_drawing("bob", "sess-x", "01", _payload(99))
    assert store.get_drawing("alice", "sess-x", "01").payload["extraction"]["equipment_count"] == 8
    assert store.get_drawing("bob", "sess-x", "01").payload["extraction"]["equipment_count"] == 99


def test_inmemory_list_returns_chronological_order():
    store = InMemoryStore()
    store.save_drawing("alice", "s", "01", _payload())
    time.sleep(0.001)
    store.save_drawing("alice", "s", "02", _payload())
    time.sleep(0.001)
    store.save_drawing("alice", "s", "03", _payload())

    listed = store.list_drawings("alice", "s")
    assert [m.drawing_id for m in listed] == ["01", "02", "03"]


def test_inmemory_last_save_wins_for_same_drawing():
    store = InMemoryStore()
    store.save_drawing("alice", "s", "01", _payload(1))
    store.save_drawing("alice", "s", "01", _payload(2))
    listed = store.list_drawings("alice", "s")
    assert len(listed) == 1
    assert listed[0].payload["extraction"]["equipment_count"] == 2


def test_inmemory_get_unknown_returns_none():
    store = InMemoryStore()
    assert store.get_drawing("nobody", "nowhere", "00") is None


def test_inmemory_list_unknown_returns_empty():
    store = InMemoryStore()
    assert store.list_drawings("nobody", "nowhere") == ()


def test_get_default_store_is_singleton():
    reset_default_store()
    a = get_default_store()
    b = get_default_store()
    assert a is b
    reset_default_store()
    c = get_default_store()
    assert c is not a


def test_event_to_memory_decodes_assistant_text():
    body = json.dumps({"drawing_id": "01", "payload": {"verdict": "pass"}})
    event = {
        "payload": [
            {"role": "USER", "text": "extract 01"},
            {"role": "ASSISTANT", "text": body},
        ],
        "eventTimestamp": 1700000000.0,
    }
    mem = _event_to_memory(event, "alice", "sess-1")
    assert mem is not None
    assert mem.drawing_id == "01"
    assert mem.payload == {"verdict": "pass"}
    assert mem.saved_at_s == 1700000000.0


def test_event_to_memory_decodes_content_block_form():
    body = json.dumps({"drawing_id": "02", "payload": {"k": "v"}})
    event = {
        "payload": [
            {"role": "USER", "content": [{"text": "extract 02"}]},
            {"role": "ASSISTANT", "content": [{"text": body}]},
        ],
    }
    mem = _event_to_memory(event, "alice", "sess-1")
    assert mem is not None
    assert mem.drawing_id == "02"
    assert mem.payload == {"k": "v"}


def test_event_to_memory_returns_none_for_non_json_assistant():
    event = {
        "payload": [{"role": "ASSISTANT", "text": "hello world"}],
    }
    assert _event_to_memory(event, "alice", "s") is None


def test_event_to_memory_returns_none_when_no_assistant():
    event = {"payload": [{"role": "USER", "text": "extract 01"}]}
    assert _event_to_memory(event, "alice", "s") is None


class _FakeMemoryClient:
    """In-process double for MemoryClient.

    Stores tuples of (memory_id, actor_id, session_id) -> list of events
    matching the public AgentCore Memory schema we depend on.
    """

    def __init__(self) -> None:
        self.events: dict[tuple[str, str, str], list[dict]] = {}

    def create_event(self, memory_id, actor_id, session_id, messages, **_):
        bucket = self.events.setdefault((memory_id, actor_id, session_id), [])
        payload = []
        for text, role in messages:
            payload.append({"role": role, "text": text})
        bucket.append({
            "payload": payload,
            "eventTimestamp": time.time(),
        })
        return {"event_id": f"ev-{len(bucket)}"}

    def list_events(self, memory_id, actor_id, session_id, **_):
        return list(self.events.get((memory_id, actor_id, session_id), []))


def test_agentcore_store_save_and_recall(monkeypatch):
    fake = _FakeMemoryClient()

    def _no_init(self, region_name=None, integration_source=None):
        return None

    # Patch MemoryClient constructor so the real boto3 client never gets built.
    from bedrock_agentcore.memory import MemoryClient
    monkeypatch.setattr(MemoryClient, "__init__", _no_init)

    store = AgentCoreStore(memory_id="mem-test", region_name="us-east-1")
    # Replace the underlying client with our fake.
    store._client = fake  # type: ignore[attr-defined]

    store.save_drawing("alice", "sess-1", "01", _payload(8))
    store.save_drawing("alice", "sess-1", "02", _payload(7))

    listed = store.list_drawings("alice", "sess-1")
    assert [m.drawing_id for m in listed] == ["01", "02"]

    got = store.get_drawing("alice", "sess-1", "01")
    assert got is not None
    assert got.payload["extraction"]["equipment_count"] == 8


def test_agentcore_store_get_picks_latest_for_drawing(monkeypatch):
    fake = _FakeMemoryClient()
    from bedrock_agentcore.memory import MemoryClient
    monkeypatch.setattr(MemoryClient, "__init__", lambda self, **_: None)

    store = AgentCoreStore(memory_id="mem-test")
    store._client = fake  # type: ignore[attr-defined]

    store.save_drawing("alice", "s", "01", _payload(1))
    store.save_drawing("alice", "s", "01", _payload(2))
    got = store.get_drawing("alice", "s", "01")
    assert got is not None
    assert got.payload["extraction"]["equipment_count"] == 2


def test_drawing_memory_is_frozen():
    mem = DrawingMemory(
        actor_id="a", session_id="s", drawing_id="01",
        payload={}, saved_at_s=0.0,
    )
    with pytest.raises(Exception):
        mem.payload = {"x": 1}  # type: ignore[misc]
