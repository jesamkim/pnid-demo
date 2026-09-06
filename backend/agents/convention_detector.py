"""Pick the right Convention for a given P&ID at runtime.

Rules:
  1. If the env var ``PNID_CONVENTION`` is set to ``isa`` or ``din``,
     honour it verbatim (skip detection).
  2. Otherwise, scan the OCR-extracted text blocks for evidence of each
     standard's grammar. Whichever wins gets returned.
  3. On a tie or empty OCR, default to ISA — it's the long-standing
     production assumption and we don't want to silently break the four
     baseline drawings.

The detector is deliberately deterministic and stateless so that
ralph-loop runs reproduce.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Sequence

from backend.agents.conventions import CONVENTIONS, DEFAULT, Convention
from backend.agents.strands_ocr import TextBlock


# ISA service-code stems (subset of the prompt list — the strongest
# signals to look for inside `<size>"-XXX-NNN-` line labels).
_ISA_SERVICE_HINTS = re.compile(
    r'\b(?:FG|NGL|OVH|RFX|RBO|BTM|PSV|RCY|FLR|DRN|CRD|EFF|ATM|VAC|NPH|KER|DIE|VGO|MS|SS|CS|GA|HS|HC)\b'
)

# Tag prefixes characteristic of each standard.
_ISA_TAG_HINTS = re.compile(r'\b(?:V-\d+|P-\d+[A-Z]?|PSV-\d+|PT-\d+|FT-\d+|TC-\d+|LIC-\d+|FIC-\d+|TIC-\d+)\b')
_DIN_TAG_HINTS = re.compile(r'\b(?:KA\d{2,4}|BA\d{2,4}|WA\d{2,4}|PA\d{2,4}|FA\d{2,4}|SA\d{2,4})\b')

# DIN flow-code suffixes — these are nearly never present on ISA drawings.
_DIN_FLOW_HINTS = re.compile(r'\b(?:NF|NV|FC|FD|FJ)\b\s+\d{3}')


@dataclass(frozen=True)
class DetectionResult:
    convention: Convention
    isa_score: int
    din_score: int
    source: str  # "env" | "ocr" | "default"


def detect_convention(ocr_blocks: Sequence[TextBlock] | None) -> DetectionResult:
    forced = (os.getenv("PNID_CONVENTION") or "").strip().lower()
    if forced in CONVENTIONS:
        return DetectionResult(
            convention=CONVENTIONS[forced],
            isa_score=-1, din_score=-1, source="env",
        )

    isa_score = 0
    din_score = 0
    if ocr_blocks:
        for b in ocr_blocks:
            t = b.text or ""
            isa_score += len(_ISA_SERVICE_HINTS.findall(t))
            isa_score += 2 * len(_ISA_TAG_HINTS.findall(t))
            din_score += 2 * len(_DIN_TAG_HINTS.findall(t))
            din_score += 3 * len(_DIN_FLOW_HINTS.findall(t))

    if din_score > isa_score:
        return DetectionResult(
            convention=CONVENTIONS["din"],
            isa_score=isa_score, din_score=din_score, source="ocr",
        )
    if isa_score > 0:
        return DetectionResult(
            convention=CONVENTIONS["isa"],
            isa_score=isa_score, din_score=din_score, source="ocr",
        )
    return DetectionResult(
        convention=DEFAULT,
        isa_score=isa_score, din_score=din_score, source="default",
    )
