"""FastAPI route tests using TestClient.

These tests exercise the routes that don't require Bedrock calls:
- /api/health
- /api/drawings
- /api/drawings/{key}/pipeline
- /api/drawings/{key}/image (uses pypdfium2 only, no AWS)
- /api/search (BM25 path; no Bedrock if query already in inverted index)
- /api/memory/* (in-memory backend)

Live LLM routes (/api/query, /api/ws/extract/*) are covered by the
verify scripts that run with AWS_PROFILE=profile2.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.agents.memory_store import InMemoryStore
from backend.api import main as api_main


client = TestClient(api_main.app)


def test_health_returns_drawing_keys():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["drawings"], list)
    assert len(body["drawings"]) > 0
    assert body["memory_backend"] in ("in-memory", "agentcore")


def test_drawings_list_has_cached_entries():
    r = client.get("/api/drawings")
    assert r.status_code == 200
    body = r.json()
    drawings = body["drawings"]
    assert len(drawings) >= 1
    sample = drawings[0]
    for field in ("key", "pdf", "verdict", "iterations_used", "counts"):
        assert field in sample
    for kind in ("equipment", "instruments", "lines", "anomalies"):
        assert kind in sample["counts"]


def test_drawing_pipeline_known_key():
    r = client.get("/api/drawings/01/pipeline")
    assert r.status_code == 200
    body = r.json()
    assert body["drawing_id"] == "01"
    assert "extraction" in body
    assert "equipment" in body["extraction"]


def test_drawing_pipeline_unknown_key_404():
    r = client.get("/api/drawings/zz/pipeline")
    assert r.status_code == 404


def test_drawing_image_returns_png():
    r = client.get("/api/drawings/01/image?dpi=72")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_drawing_image_unknown_key_404():
    r = client.get("/api/drawings/zz/image")
    assert r.status_code == 404


def test_drawing_geometry_returns_ground_truth():
    r = client.get("/api/drawings/01/geometry")
    assert r.status_code == 200
    body = r.json()
    assert body["drawing_id"] == "01"
    assert body["source"] == "ground_truth"
    assert body["canvas"]["width"] > 0 and body["canvas"]["height"] > 0
    assert len(body["equipment"]) > 0
    sample = body["equipment"][0]
    assert "tag" in sample and "bbox" in sample
    assert isinstance(sample["bbox"], list) and len(sample["bbox"]) == 4
    assert isinstance(body["lines"], list)


def test_drawing_geometry_unknown_404():
    r = client.get("/api/drawings/zz/geometry")
    assert r.status_code == 404


def test_search_returns_hits_for_known_tag():
    """The cached index has 4 drawings; V-101 should be present."""
    r = client.post("/api/search", json={"query": "V-101", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "V-101"
    assert isinstance(body["hits"], list)
    # BM25 path: V-101 must surface in at least one hit's text.
    assert any("V-101" in h["text"] for h in body["hits"])


def test_search_kind_filter():
    r = client.post(
        "/api/search",
        json={"query": "instrument", "top_k": 5, "kind_filter": "instrument"},
    )
    assert r.status_code == 200
    body = r.json()
    assert all(h["kind"] == "instrument" for h in body["hits"])


def test_memory_recall_unknown_404():
    api_main._set_memory_for_test(InMemoryStore())
    r = client.get("/api/memory/no-session/00")
    assert r.status_code == 404


def test_memory_list_empty_session():
    api_main._set_memory_for_test(InMemoryStore())
    r = client.get("/api/memory/empty-session")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["drawings"] == []
    assert body["session_id"] == "empty-session"


def test_memory_save_then_recall():
    store = InMemoryStore()
    api_main._set_memory_for_test(store)
    payload = {
        "verdict": "pass",
        "iterations_used": 0,
        "total_elapsed_s": 12.0,
        "extraction": {"equipment": [{}, {}], "instruments": [{}],
                       "lines": [], "connections": []},
        "anomalies": [],
    }
    store.save_drawing("demo-presenter", "abc", "01", payload)

    r = client.get("/api/memory/abc/01")
    assert r.status_code == 200
    body = r.json()
    assert body["drawing_id"] == "01"
    assert body["summary"]["counts"]["equipment"] == 2
    assert body["summary"]["verdict"] == "pass"


def test_memory_actor_id_query_param():
    store = InMemoryStore()
    api_main._set_memory_for_test(store)
    store.save_drawing("alice", "s1", "01", {
        "extraction": {"equipment": [{}], "instruments": [], "lines": [], "connections": []},
        "anomalies": [],
    })
    # Default actor finds nothing in alice's session.
    r1 = client.get("/api/memory/s1")
    assert r1.json()["count"] == 0
    # Explicit actor_id finds the entry.
    r2 = client.get("/api/memory/s1?actor_id=alice")
    assert r2.json()["count"] == 1
    assert r2.json()["drawings"][0]["drawing_id"] == "01"


def test_memory_list_returns_chronological():
    store = InMemoryStore()
    api_main._set_memory_for_test(store)
    base = {
        "extraction": {"equipment": [], "instruments": [], "lines": [], "connections": []},
        "anomalies": [],
    }
    for did in ("01", "02", "03"):
        store.save_drawing("demo-presenter", "ord", did, dict(base))
    r = client.get("/api/memory/ord")
    body = r.json()
    assert [d["drawing_id"] for d in body["drawings"]] == ["01", "02", "03"]
