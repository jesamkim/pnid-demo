"""Cross-session memory for the P&ID Agentic pipeline.

Two backends behind the same protocol:
- InMemoryStore: process-local dict, used for tests and offline demos.
- AgentCoreStore: thin wrapper over bedrock_agentcore.memory.MemoryClient
  so each extraction run is persisted as an event under
  (memory_id, actor_id, session_id) and can be recalled in later turns.

A "drawing memory" is one event per (session, drawing_id). The payload is
JSON-encoded as the assistant message, the user message holds the request
intent ("extract <drawing_id>"). This matches AgentCore's conversational
schema while letting us round-trip structured extraction results.

The store is intentionally minimal — Phase 3.0g only needs save / list /
get. AgentCore's semantic strategies (LTM facts, summaries) can be layered
on later without changing the public API here.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class DrawingMemory:
    actor_id: str
    session_id: str
    drawing_id: str
    payload: dict
    saved_at_s: float


class MemoryStore(Protocol):
    def save_drawing(
        self, actor_id: str, session_id: str, drawing_id: str, payload: dict
    ) -> DrawingMemory: ...

    def list_drawings(
        self, actor_id: str, session_id: str
    ) -> tuple[DrawingMemory, ...]: ...

    def get_drawing(
        self, actor_id: str, session_id: str, drawing_id: str
    ) -> Optional[DrawingMemory]: ...


class InMemoryStore:
    """Process-local backend. Last save wins per (actor, session, drawing)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._data: dict[tuple[str, str], dict[str, DrawingMemory]] = {}

    def _key(self, actor_id: str, session_id: str) -> tuple[str, str]:
        return (actor_id, session_id)

    def save_drawing(
        self, actor_id: str, session_id: str, drawing_id: str, payload: dict
    ) -> DrawingMemory:
        mem = DrawingMemory(
            actor_id=actor_id,
            session_id=session_id,
            drawing_id=drawing_id,
            payload=payload,
            saved_at_s=time.time(),
        )
        with self._lock:
            bucket = self._data.setdefault(self._key(actor_id, session_id), {})
            bucket[drawing_id] = mem
        return mem

    def list_drawings(
        self, actor_id: str, session_id: str
    ) -> tuple[DrawingMemory, ...]:
        with self._lock:
            bucket = self._data.get(self._key(actor_id, session_id), {})
            items = sorted(bucket.values(), key=lambda m: m.saved_at_s)
        return tuple(items)

    def get_drawing(
        self, actor_id: str, session_id: str, drawing_id: str
    ) -> Optional[DrawingMemory]:
        with self._lock:
            bucket = self._data.get(self._key(actor_id, session_id), {})
            return bucket.get(drawing_id)


class AgentCoreStore:
    """AgentCore Memory backend.

    `memory_id` must already exist (created out-of-band via
    MemoryClient.create_memory_and_wait). We don't auto-create on first
    save because creation is an asynchronous, account-wide operation
    that doesn't belong on the request path.
    """

    _USER_TEMPLATE = "extract {drawing_id}"

    def __init__(self, memory_id: str, region_name: Optional[str] = None) -> None:
        # Imported lazily so unit tests don't need the SDK.
        from bedrock_agentcore.memory import MemoryClient

        self._memory_id = memory_id
        self._client = MemoryClient(region_name=region_name)

    def save_drawing(
        self, actor_id: str, session_id: str, drawing_id: str, payload: dict
    ) -> DrawingMemory:
        body = json.dumps(_envelope(drawing_id, payload), ensure_ascii=False)
        self._client.create_event(
            memory_id=self._memory_id,
            actor_id=actor_id,
            session_id=session_id,
            messages=[
                (self._USER_TEMPLATE.format(drawing_id=drawing_id), "USER"),
                (body, "ASSISTANT"),
            ],
        )
        return DrawingMemory(
            actor_id=actor_id,
            session_id=session_id,
            drawing_id=drawing_id,
            payload=payload,
            saved_at_s=time.time(),
        )

    def list_drawings(
        self, actor_id: str, session_id: str
    ) -> tuple[DrawingMemory, ...]:
        events = self._client.list_events(
            memory_id=self._memory_id,
            actor_id=actor_id,
            session_id=session_id,
            include_payload=True,
        )
        out: list[DrawingMemory] = []
        for ev in events:
            mem = _event_to_memory(ev, actor_id, session_id)
            if mem is not None:
                out.append(mem)
        out.sort(key=lambda m: m.saved_at_s)
        return tuple(out)

    def get_drawing(
        self, actor_id: str, session_id: str, drawing_id: str
    ) -> Optional[DrawingMemory]:
        # Latest event for this drawing_id wins.
        latest: Optional[DrawingMemory] = None
        for mem in self.list_drawings(actor_id, session_id):
            if mem.drawing_id == drawing_id:
                latest = mem
        return latest


def _envelope(drawing_id: str, payload: dict) -> dict:
    return {"drawing_id": drawing_id, "payload": payload}


def _event_to_memory(
    event: dict[str, Any], actor_id: str, session_id: str
) -> Optional[DrawingMemory]:
    """Best-effort decode of an AgentCore event into a DrawingMemory."""
    payload_msgs = event.get("payload") or []
    assistant_text: Optional[str] = None
    for m in payload_msgs:
        # AgentCore returns either {"role": "ASSISTANT", "content": [{"text": ...}]}
        # or a flatter {"role": "ASSISTANT", "text": ...} depending on SDK version.
        role = (m.get("role") or m.get("messageRole") or "").upper()
        if role != "ASSISTANT":
            continue
        if isinstance(m.get("text"), str):
            assistant_text = m["text"]
        else:
            content = m.get("content") or []
            for c in content:
                if isinstance(c, dict) and isinstance(c.get("text"), str):
                    assistant_text = c["text"]
                    break
    if not assistant_text:
        return None
    try:
        decoded = json.loads(assistant_text)
    except json.JSONDecodeError:
        return None
    drawing_id = decoded.get("drawing_id")
    payload = decoded.get("payload")
    if not isinstance(drawing_id, str) or not isinstance(payload, dict):
        return None
    ts = event.get("eventTimestamp") or event.get("event_timestamp")
    saved_at_s = _coerce_timestamp(ts)
    return DrawingMemory(
        actor_id=actor_id,
        session_id=session_id,
        drawing_id=drawing_id,
        payload=payload,
        saved_at_s=saved_at_s,
    )


def _coerce_timestamp(raw: Any) -> float:
    if raw is None:
        return time.time()
    try:
        return float(raw.timestamp())  # datetime
    except AttributeError:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return time.time()


_DEFAULT: Optional[MemoryStore] = None


def get_default_store() -> MemoryStore:
    """Return a process-wide singleton InMemoryStore.

    Production deployments wire AgentCoreStore directly via dependency
    injection (see agent_main.py); this default exists so tests and
    local demos work with zero AWS calls.
    """
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = InMemoryStore()
    return _DEFAULT


def reset_default_store() -> None:
    """Test-only: clear the singleton so each test gets a fresh store."""
    global _DEFAULT
    _DEFAULT = None
