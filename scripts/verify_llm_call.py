"""Verify Opus 4.7 + Sonnet 4.6 invoke with 1M context beta header."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.llm_client import call_primary, call_secondary


def run(label: str, fn) -> bool:
    print(f"\n=== {label} ===")
    try:
        r = fn(
            "Reply with exactly the JSON: {\"ok\": true, \"who\": \"<your model name>\"}",
            system="You are a P&ID extraction agent test ping.",
            max_tokens=100,
        )
        print(f"  model_id   : {r.model_id}")
        print(f"  stop_reason: {r.stop_reason}")
        print(f"  tokens     : in={r.input_tokens} out={r.output_tokens}")
        print(f"  text       : {r.text!r}")
        return "ok" in r.text.lower() or '"ok"' in r.text
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        return False


def main() -> int:
    pri = run("PRIMARY: Opus 4.7", call_primary)
    sec = run("SECONDARY: Sonnet 4.6", call_secondary)
    print(f"\n=== RESULT ===\nPrimary: {'PASS' if pri else 'FAIL'}\nSecondary: {'PASS' if sec else 'FAIL'}")
    return 0 if (pri and sec) else 1


if __name__ == "__main__":
    sys.exit(main())
