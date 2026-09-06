"""Verify primary/secondary model IDs are accessible in the configured region.

Runs: lists foundation models and inference profiles, checks Opus 4.8 / Sonnet 4.6 / Cohere Embed v4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.aws_clients import get_bedrock
from backend.config import get_settings


def main() -> int:
    s = get_settings()
    bedrock = get_bedrock()

    targets = {
        "primary": s.primary_model.id,
        "secondary": s.secondary_model.id,
        "embedding": s.embedding_id,
    }

    print(f"Profile={s.aws_profile} Region={s.aws_region}")
    print(f"Targets: {json.dumps(targets, indent=2)}\n")

    print("=== list_foundation_models ===")
    fm = bedrock.list_foundation_models()
    fm_ids = {m["modelId"] for m in fm["modelSummaries"]}
    for label, mid in targets.items():
        bare = mid.split(".", 1)[1] if "." in mid else mid
        match = [x for x in fm_ids if bare in x or mid in x]
        print(f"  {label} ({mid}): {'FOUND' if match else 'NOT in foundation models'}")
        if match:
            for m in match[:3]:
                print(f"      - {m}")

    print("\n=== list_inference_profiles ===")
    try:
        profiles = bedrock.list_inference_profiles()
        prof_ids = {p["inferenceProfileId"] for p in profiles.get("inferenceProfileSummaries", [])}
        for label, mid in targets.items():
            match = [p for p in prof_ids if mid in p or mid.split(".")[-2] in p]
            print(f"  {label} ({mid}): {'FOUND profile' if match else 'no profile match'}")
            if match:
                for p in match[:3]:
                    print(f"      - {p}")
    except Exception as e:
        print(f"  inference profiles error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
