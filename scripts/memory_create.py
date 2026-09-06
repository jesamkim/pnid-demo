"""Create (or fetch) the AgentCore Memory used for cross-session recall.

The demo's `memory_store.AgentCoreStore` resolves
`BEDROCK_AGENTCORE_MEMORY_ID` at process start; this script writes a
memory once per account/region and prints the id so we can wire it
into the AppStack environment.

Run:
    AWS_PROFILE=profile2 python3 scripts/memory_create.py
"""
from __future__ import annotations

import os
import sys

from bedrock_agentcore.memory import MemoryClient


REGION = os.environ.get("AWS_REGION", "us-east-1")
NAME = "pnid_demo_memory"


def main() -> None:
    client = MemoryClient(region_name=REGION)
    print(f"creating memory (or fetching existing) name={NAME!r} region={REGION}")
    mem = client.create_or_get_memory(
        name=NAME,
        description="P&ID demo cross-session memory (drawings + extractions)",
        event_expiry_days=30,
        strategies=[],  # short-term memory only; LTM strategies can be layered later
    )
    mem_id = mem.get("id") or mem.get("memoryId") or mem.get("memory", {}).get("id")
    print(f"\nMemory id: {mem_id}")
    print("\nNext: redeploy AppStack with this env var:")
    print(f"  export BEDROCK_AGENTCORE_MEMORY_ID={mem_id}")


if __name__ == "__main__":
    sys.exit(main())
