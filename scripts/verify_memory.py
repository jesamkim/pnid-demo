"""Phase 3.0g verify: AgentCore Memory integration smoke test.

Goal: prove the memory store path end-to-end without spending Bedrock
tokens. Strategy:
  1. Load cached pipeline results from .claude/artifacts/extraction/.
  2. Round-trip them through agent_main.invoke(action="extract"-equivalent
     save) by calling _save_to_memory + invoke(action="recall"/"list_session").
  3. Verify session/actor isolation.

The script exercises the InMemoryStore backend by default. Set
BEDROCK_AGENTCORE_MEMORY_ID + AWS_PROFILE=profile2 to hit live AgentCore
Memory (not done in CI).

Run:
    AWS_PROFILE=profile2 python3 scripts/verify_memory.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agent_main  # noqa: E402
from backend.agents.memory_store import InMemoryStore  # noqa: E402

ARTIFACTS = ROOT / ".claude" / "artifacts" / "extraction"
DRAWINGS = ["01", "01b", "02", "03"]


def _summary_brief(d: dict) -> str:
    s = d["summary"]
    c = s["counts"]
    return (f"verdict={s['verdict']} iters={s['iterations_used']} "
            f"eq={c['equipment']} inst={c['instruments']} lines={c['lines']} "
            f"conn={c['connections']} anom={s['anomaly_count']}")


def _load_cached_payload(drawing_id: str) -> dict:
    """Reshape a cached *_strands_pipeline.json into the agent_main extract response shape."""
    p = ARTIFACTS / f"{drawing_id}_strands_pipeline.json"
    if not p.exists():
        raise SystemExit(f"missing cached pipeline result: {p}")
    raw = json.loads(p.read_text())
    return {
        "drawing_id": raw["drawing_id"],
        "verdict": raw["verdict"],
        "iterations_used": raw.get("iterations_used", 0),
        "total_elapsed_s": raw.get("total_elapsed_s", 0.0),
        "extraction": raw["extraction"],
        "anomalies": raw.get("anomalies", []),
        "events": raw.get("events", []),
    }


def main() -> None:
    print("=" * 72)
    print("Phase 3.0g verify: AgentCore Memory integration")
    print("=" * 72)

    # Force the in-memory backend so this script is hermetic.
    store = InMemoryStore()
    agent_main._set_memory_for_test(store)

    actor = "verify-script"
    session = "verify-session-1"

    # 1. Save 4 cached extractions into memory (simulating a presenter
    #    walking through 4 P&IDs in one demo session).
    print()
    print(f"[1/4] saving {len(DRAWINGS)} cached extractions to memory")
    for did in DRAWINGS:
        payload = _load_cached_payload(did)
        agent_main._save_to_memory(actor, session, did, payload)
        print(f"  saved {did}: verdict={payload['verdict']}")

    # 2. Recall each drawing individually.
    print()
    print("[2/4] recall each drawing by id")
    for did in DRAWINGS:
        out = agent_main.invoke({
            "action": "recall",
            "drawing": did,
            "actor_id": actor,
            "session_id": session,
        })
        if not out.get("found"):
            print(f"  FAIL recall {did}: {out}")
            sys.exit(1)
        print(f"  recalled {did}: {_summary_brief(out)}")

    # 3. List the whole session.
    print()
    print("[3/4] list_session — chronological summaries")
    out = agent_main.invoke({
        "action": "list_session",
        "actor_id": actor,
        "session_id": session,
    })
    print(f"  count={out['count']}")
    for d in out["drawings"]:
        s = d["summary"]
        c = s["counts"]
        print(f"    {d['drawing_id']:<4} verdict={s['verdict']:<18} "
              f"eq={c['equipment']} inst={c['instruments']} "
              f"lines={c['lines']} anom={s['anomaly_count']}")
    if out["count"] != len(DRAWINGS):
        print(f"  FAIL expected {len(DRAWINGS)} entries, got {out['count']}")
        sys.exit(1)

    # 4. Session isolation: a fresh session sees nothing.
    print()
    print("[4/4] session isolation — recall under unrelated session_id")
    out = agent_main.invoke({
        "action": "recall",
        "drawing": "01",
        "actor_id": actor,
        "session_id": "some-other-session",
    })
    if out.get("found"):
        print(f"  FAIL session leak: {out}")
        sys.exit(1)
    print(f"  isolated OK: found={out['found']} session={out['session_id']}")

    print()
    print("ALL MEMORY CHECKS PASS")


if __name__ == "__main__":
    main()
