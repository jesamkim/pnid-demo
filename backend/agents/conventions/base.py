"""Convention base type — everything an agent needs for one P&ID standard."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from backend.schemas import Anomaly, ExtractionResult


@dataclass(frozen=True)
class Convention:
    """Per-standard configuration injected into the agent pipeline.

    Fields are deliberately data-only (no behaviour) so the orchestrator
    can swap one Convention for another without re-wiring agents.

    - `name` — short id, "isa" or "din". Used by detectors and logs.
    - `display_name` — human-readable, e.g. "ISA-5.1 (North America)".
    - `extractor_system_prompt` — full SYSTEM string given to the Vision
      agent. Embeds the standard's tag conventions and verbatim rules.
    - `summary_safety_label` — short Korean phrase used inside the
      summary agent prompt, e.g. "ISA-5.1 룰" or "P&ID 안전 룰".
    - `line_no_regex` — compiled regex matching that standard's line
      label grammar. Used by line_refinement and OCR candidate filter.
    - `service_codes_help` — one-liner describing which service codes
      to expect (used in detect heuristics + summary text).
    - `psv_synonyms` — set of Equipment.type values that count as a
      pressure-relief device on this standard ({"psv"} for ISA,
      {"safety_valve", "psv"} for DIN — DIN often labels the symbol as
      Sicherheitsventil but ISA-style "psv" is also valid).
    - `psv_target_pattern` — regex picking up vessel tags inside a
      PSV.service string. ISA = `V-\\d+|T-\\d+`. DIN = `BA\\d+|KA\\d+`.
    - `anomaly_rules` — tuple of rule functions. Each takes
      ExtractionResult and returns tuple[Anomaly, ...]. Convention
      drives which rules apply (e.g. DIN drops vessel_without_psv
      because PSV symbol position is harder to ground).
    """

    name: str
    display_name: str
    extractor_system_prompt: str
    summary_safety_label: str
    line_no_regex: re.Pattern
    service_codes_help: str
    psv_synonyms: frozenset[str]
    psv_target_pattern: re.Pattern
    anomaly_rules: tuple[Callable[[ExtractionResult], tuple[Anomaly, ...]], ...]
