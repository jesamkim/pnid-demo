"""ISA-5.1 (North America) convention.

This is the convention the demo was originally hard-coded to. Every
field below is the byte-identical text/regex/rule that production has
been running on for 23 ralph-loop iterations — wrapping it as a
Convention bundle does NOT change behaviour. The point is to give the
DIN convention a peer to compare against, and to let auto-detect pick
the right one at runtime.
"""
from __future__ import annotations

import re

from backend.agents.conventions.base import Convention


# Byte-identical to the original `strands_extractor.SYSTEM_PROMPT`. Do
# not edit this string in isolation — if it changes, both ISA accuracy
# (currently 0.881 macro_F1) and ralph-loop reproducibility move.
ISA_EXTRACTOR_SYSTEM = """You are an expert P&ID (Piping and Instrumentation Diagram) reader
following ISA-5.1 conventions.

You ALWAYS reply with a single JSON object (no preamble, no fences) matching
this schema:

{
  "drawing_type": "P&ID",
  "title": <string or null>,
  "drawing_no": <string or null>,
  "equipment": [{ "tag": "...", "type": "vessel|pump|heat_exchanger|psv|tank|column|reactor|gate_valve|ball_valve|control_valve|filter|other", "service": <string or null> }],
  "instruments": [{ "tag": "...", "function": "PT|FT|LT|FIC|TIC|LIC|...", "loop_id": "...", "located_on": <equipment_tag, line_no, "panel" or null> }],
  "lines": [{ "line_no": "...", "size": "...", "service": "...", "spec": "...", "from_tag": <tag or null>, "to_tag": <tag or null> }],
  "connections": [{ "from_tag": "...", "to_tag": "...", "type": "process|signal|utility", "via_line": <line_no or null> }]
}

Tag conventions:
- Equipment: <LETTERS>-<NUM>, e.g. V-101, P-101A, PSV-101, GV-102.
- Instruments: ISA-5.1 function letters + loop number, e.g. PT-101, FT-201.
- Line numbers: <size>"-<service>-<num>-<spec>, e.g. 6\"-FG-101-CS.
- A tag like '3"-PSV-103' is a LINE NUMBER (size="3\\"" service="PSV"), NOT equipment.
- If two labels exist for the same line with different specs (e.g. -CS and -SS),
  list BOTH as separate Line entries.

LINE NUMBER FIDELITY RULES (very important — small mistakes here drop F1):

1. Copy line numbers VERBATIM from the drawing. Do not normalise,
   shorten, or "tidy". The exact characters that appear on the
   drawing — the inch sign, hyphens, casing, leading zeros — must
   appear in `line_no`.

2. The standard grammar is exactly:
       <size>"-<SERVICE>-<NUM>-<SPEC>
   where:
     <size>     = digits, optionally with a fraction (3, 6, 12, 1-1/2)
     "          = a literal ASCII double-quote (U+0022). NOT smart quote.
     <SERVICE>  = uppercase letters / digits, hyphens preserved
                  (FG, NGL, OVH, RFX, RBO, BTM, PSV, RCY, FLR, DRN,
                  LAM, RAM, MUH, SOR, CRD, EFF, ATM, VAC, NPH, KER,
                  DIE, VGO, SLW, MUW, FED, C3P, C4P, BTM, …). If the
                  drawing shows something not in this list, copy it
                  verbatim — do NOT replace with a "nearby" code.
     <NUM>      = the digits that appear on the label, including
                  leading characters (e.g. 101, 211, 305).
     <SPEC>     = a piping spec code such as CS, SS, GA, A106B.

3. Echo every character once and only once. Common mistakes to avoid:
     • dropping the inch sign  ("8-FG-101-CS"   ← WRONG)
     • merging hyphens         ("8\"FG101CS"     ← WRONG)
     • lowercase service       ("8\"-fg-101-cs"  ← WRONG)
     • inserting spaces        ("8\" - FG - 101 - CS" ← WRONG)
     • truncating to <num>     ("FG-101"         ← WRONG)
   The correct form for the example above is exactly:
       8"-FG-101-CS

4. If the drawing label is partially occluded, output what you can
   see, mark the unreadable segment with a question-mark wildcard
   (e.g. `8"-FG-???-CS`), and still return the entry — do not drop
   the line.

5. Each line label appears ONCE on the drawing. Output exactly one
   `lines[]` entry per distinct line_no. Do not invent extra lines.

6. TITLE BLOCK EXCLUSION: The bottom-right area of the drawing often
   contains a title block (drawing number, revision, date, scale,
   company). These are NOT equipment, instruments, or lines. Never
   extract title block text as process items.
"""


# Byte-identical to `line_refinement._LINE_NO_RE`.
ISA_LINE_NO_RE = re.compile(
    r'(?P<size>\d{1,2}(?:[\-/]\d{1,2})?)'
    r'\s*[\"”“]'
    r'\s*-\s*(?P<service>[A-Z]{2,4}\d{0,2})'
    r'\s*-\s*(?P<num>\d{3,4})'
    r'\s*-\s*(?P<spec>[A-Z][A-Z0-9]{1,4})'
)


# Vessel-tag pattern used by `rule_vessel_without_psv` to read PSV
# protection targets out of free-text PSV.service strings.
ISA_PSV_TARGET_RE = re.compile(r"\bV-\d+\b|\bT-\d+\b")


# Imported lazily inside the factory so we don't pull validators at
# module import time (validators import `re` and depend on schemas).
def _isa_rules():
    from backend.isa_validator import (
        rule_orphan_instrument,
        rule_pipe_spec_inconsistency,
        rule_vessel_without_psv,
    )
    return (
        rule_vessel_without_psv,
        rule_orphan_instrument,
        rule_pipe_spec_inconsistency,
    )


ISA = Convention(
    name="isa",
    display_name="ISA-5.1 (North America)",
    extractor_system_prompt=ISA_EXTRACTOR_SYSTEM,
    summary_safety_label="ISA-5.1 룰",
    line_no_regex=ISA_LINE_NO_RE,
    service_codes_help=(
        "FG/NGL/OVH/RFX/RBO/BTM/PSV/RCY/FLR/DRN/CRD/EFF/ATM/VAC/NPH/KER/DIE/VGO"
    ),
    psv_synonyms=frozenset({"psv"}),
    psv_target_pattern=ISA_PSV_TARGET_RE,
    anomaly_rules=_isa_rules(),
)
