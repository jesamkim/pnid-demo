"""Phase 3.1 verify: live uvicorn + cached routes + memory routes.

Boots uvicorn in a background thread, then exercises every non-Bedrock
route. Bedrock-dependent routes (/api/query, ws_extract) are intentionally
skipped here because they are covered by Phase 1/2/3.0f verify scripts.

Run:
    python3 scripts/verify_api.py
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from backend.agents.memory_store import InMemoryStore  # noqa: E402
from backend.api import main as api_main  # noqa: E402

PORT = 18801
BASE = f"http://127.0.0.1:{PORT}"


def _start_server() -> threading.Thread:
    config = uvicorn.Config(api_main.app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)

    def run() -> None:
        server.run()

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # Wait until /api/health is reachable.
    deadline = time.time() + 8.0
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE}/api/health", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    else:
        raise SystemExit("uvicorn did not become healthy in 8s")

    return t


def main() -> None:
    print("=" * 72)
    print("Phase 3.1 verify: FastAPI live routes")
    print("=" * 72)

    # Use a clean in-memory backend for the memory routes.
    api_main._set_memory_for_test(InMemoryStore())

    _start_server()

    # 1. health
    r = httpx.get(f"{BASE}/api/health", timeout=5.0)
    print(f"[health] {r.status_code} {r.json()}")
    assert r.status_code == 200 and r.json()["status"] == "ok"

    # 2. drawings (cached)
    r = httpx.get(f"{BASE}/api/drawings", timeout=10.0)
    drawings = r.json()["drawings"]
    print(f"[drawings] count={len(drawings)}")
    for d in drawings:
        print(f"  {d['key']:<4} verdict={d['verdict']:<18} counts={d['counts']}")

    # 3. one drawing pipeline
    r = httpx.get(f"{BASE}/api/drawings/01/pipeline", timeout=5.0)
    pipe = r.json()
    print(f"[pipeline 01] verdict={pipe['verdict']} elapsed_s={pipe.get('total_elapsed_s')}")

    # 4. one drawing image (smaller dpi to keep this quick)
    r = httpx.get(f"{BASE}/api/drawings/01/image?dpi=72", timeout=15.0)
    print(f"[image 01] {r.status_code} {len(r.content)} bytes ct={r.headers.get('content-type')}")
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"

    # 5. search
    r = httpx.post(
        f"{BASE}/api/search",
        json={"query": "PSV protecting V-101", "top_k": 5},
        timeout=10.0,
    )
    body = r.json()
    print(f"[search] {len(body['hits'])} hits for {body['query']!r}")
    for h in body["hits"][:3]:
        print(f"  drawing={h['drawing_id']} kind={h['kind']} tag={h['tag']} "
              f"score={h['score']}")

    # 6. memory list/recall round-trip via the API
    actor = "demo-presenter"
    session = "verify-session"
    api_main._memory().save_drawing(actor, session, "01", {
        "verdict": "pass",
        "iterations_used": 0,
        "total_elapsed_s": 12.0,
        "extraction": {"equipment": [{}, {}], "instruments": [{}, {}, {}],
                       "lines": [], "connections": []},
        "anomalies": [],
    })
    r = httpx.get(f"{BASE}/api/memory/{session}", timeout=5.0)
    print(f"[memory list] {r.json()}")
    r = httpx.get(f"{BASE}/api/memory/{session}/01", timeout=5.0)
    print(f"[memory recall] verdict={r.json()['summary']['verdict']} "
          f"counts={r.json()['summary']['counts']}")

    # 7. memory unknown -> 404
    r = httpx.get(f"{BASE}/api/memory/no-session/zz", timeout=5.0)
    print(f"[memory recall unknown] {r.status_code}")
    assert r.status_code == 404

    print()
    print("ALL FASTAPI ROUTES PASS")


if __name__ == "__main__":
    main()
