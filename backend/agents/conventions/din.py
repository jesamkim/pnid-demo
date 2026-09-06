"""DIN EN 10628 + DIN 19227 (Europe / Germany) convention.

Calibrated against UER-1234567 (Reaktion Str.1, Teil 2 / Musterfließbild)
which uses the canonical DIN equipment prefixes:

    KA — Kolonne (column / tower)
    BA — Behälter (vessel / drum)
    WA — Wärmetauscher (heat exchanger / condenser)
    PA — Pumpe (pump)
    FA — Filter
    SA — Sicherheitsventil (safety valve, ISA-equivalent: PSV)

and DIN 19227 instrument letters:

    TI / TIC / TRC — Temperatur (PV / control / record-control)
    PI / PIC / PRC — Druck (pressure)
    LI / LIC / LRC — Niveau (level)
    FI / FIC / FRC — Durchfluss (flow)
    YS — Stellungsmelder (position switch)
    PDI — Differenzdruck

Line labels follow `L<series>.<location>-<size>-<spec> <flow><Z-code>`,
e.g. `LR040.22040-80-40C1200 NF 223`. The two-letter `NF/NV/FC/FD/FJ`
code right after the inch-style spec marks Normal Flow / Normal Vent /
Fail-Closed / Fail-Drain etc. — those are part of the line label, not
a separate column.
"""
from __future__ import annotations

import re

from backend.agents.conventions.base import Convention


DIN_EXTRACTOR_SYSTEM = """You are an expert P&ID (Piping and Instrumentation Diagram) reader
following DIN EN 10628 (graphical symbols) and DIN 19227 (instrument
function letters), as used in European / German engineering drawings.

You ALWAYS reply with a single JSON object (no preamble, no fences) matching
this schema:

{
  "drawing_type": "P&ID",
  "title": <string or null>,
  "drawing_no": <string or null>,
  "equipment": [{ "tag": "...", "type": "vessel|pump|heat_exchanger|psv|safety_valve|tank|column|reactor|gate_valve|ball_valve|control_valve|filter|vacuum_unit|other", "service": <string or null> }],
  "instruments": [{ "tag": "...", "function": "TI|TIC|TRC|PI|PIC|PRC|LI|LIC|FI|FIC|FRC|YS|PDI|...", "loop_id": "...", "located_on": <equipment_tag, line_no, "panel" or null> }],
  "lines": [{ "line_no": "...", "size": "...", "service": "...", "spec": "...", "from_tag": <tag or null>, "to_tag": <tag or null> }],
  "connections": [{ "from_tag": "...", "to_tag": "...", "type": "process|signal|utility", "via_line": <line_no or null> }]
}

Tag conventions (DIN equipment prefixes):
- Equipment uses two-letter prefix + number, no hyphen, e.g. KA002, BA101, WA008, PA104.
  - KA -> column / Kolonne (type="column")
  - BA -> vessel / drum / Behälter (type="vessel" if pressure, "tank" if atmospheric)
  - WA -> heat exchanger / condenser / Wärmetauscher (type="heat_exchanger")
  - PA -> pump / Pumpe (type="pump")
  - FA -> filter (type="filter")
  - SA -> safety valve / Sicherheitsventil (type="safety_valve" — same role as ISA PSV)
- The `service` field should carry the German function name when visible
  on the drawing, e.g. "Glockenbodenkolonne", "Destillatbehälter",
  "Kreiselpumpe", "Umlaufverdampfer". Copy verbatim, do not translate.

Tag conventions (DIN instrument letters, DIN 19227):
- First letter: measured variable (T, P, L, F, A, D, ...)
- Second letter: I=Indication, R=Recording, C=Control, S=Switch
- Third (optional): redundancy or function suffix
- Loop ID is typically a free identifier like "T0029", "F0025", "L0012"
  attached underneath the bubble. The instrument tag becomes
  "<function>-<loop_id>" e.g. "TRC-T0029".

Line label conventions:
- Line numbers look like `L<series>.<location>-<size>-<spec> <flow><Z-code>`
  e.g. `LR040.22040-80-40C1200 NF 223` or `LA01-LR024.10000-25-10H1200 NV 221`.
- `NF`, `NV`, `FC`, `FD`, `FJ` are part of the line label (Normal Flow,
  Normal Vent, Fail Closed, Fail Drain, Fail Jam). Keep them in the
  verbatim `line_no` string.
- The trailing 3-digit number (e.g. 221, 216, 223) is the design code
  (Werkstoff- / Druckstufe). Keep it in `line_no`.

LINE NUMBER FIDELITY RULES (apply verbatim — DIN tolerates dots and
spaces inside the label, do not normalise them away):

1. Copy line numbers VERBATIM. Do not drop the dot, do not collapse
   spaces, do not change letter case.

2. If a single label spans two lines on the drawing (which is common
   in DIN P&IDs, e.g. `LR033` over `12000-80-10B1213 NV 221`), output
   the full reconstructed string `LR033.12000-80-10B1213 NV 221`.

3. If the drawing label is partially occluded, output what you can
   see, mark the unreadable segment with a question-mark wildcard
   (e.g. `LR0??.22040-80-40C1200 NF 223`), and still return the entry
   — do not drop the line.

4. Each line label appears ONCE on the drawing. Output exactly one
   `lines[]` entry per distinct line_no.

INSTRUMENT GROUNDING RULES (DIN bubbles need spatial reasoning):

5. DIN instrument bubbles are typically rendered as small circles with
   the function letters on top and the loop_id below, often connected
   to equipment by a short horizontal/vertical line stub. To determine
   `located_on`:
   - If the bubble sits directly above or beside an equipment symbol
     (within ~2 bubble-widths), set `located_on` to that equipment tag
     (e.g. TRC-T0029 placed at the side of KA002 -> located_on="KA002").
   - If the bubble is connected to a process line via a short stub,
     set `located_on` to the relevant `line_no`.
   - If neither is clear, set `located_on` to "panel" (for pure
     control-room indicators like alarms YS) — do NOT leave it null
     unless the bubble is genuinely floating with no nearby symbol.
   The goal is to ground EVERY instrument; orphan instruments (null
   located_on with no signal connection) are extraction failures.

6. When the same equipment carries multiple instruments (e.g. KA002
   has TRC-T0029, TRC-T0031, FRC-F0025, LIC-L0011, LIC-L0012, LIC-L0013
   stacked vertically along the column), list them ALL with
   located_on="KA002". Repeat the equipment tag freely.

EQUIPMENT vs UTILITY-LABEL DISAMBIGUATION (CRITICAL — DIN drawings
sprinkle inflow / outflow labels around the page edges that look like
equipment if you only read the prefix):

7. Drawing-edge text describing an external stream — e.g.
   "Kühlwasser, 20 °C", "Kühlwasser-Rücklauf", "Zur Abluftreinigung",
   "Von Konzentration", "Kondensat aus Heizdampf" — is a UTILITY
   ANNOTATION, NOT an equipment item. NEVER emit such phrases as
   `service` of a fabricated `BA00x` / `PA1xx` / `WA1xx` equipment.
   These annotations describe where a process line ENTERS or EXITS
   the page, and belong (if anything) in the corresponding `Line`
   entry's `service` field, not as standalone equipment.

8. Within the page frame the drawing shows ONE column (KA002), four
   to five vessels (BA100..BA103), five heat exchangers
   (WA006..WA010), six pumps (PA100..PA105), one safety valve
   (AS001), and one vacuum unit (Vakuumstation). Anything OUTSIDE
   this set with a BA/PA/WA prefix and a free-form German service
   name is almost certainly a misread of an inflow / outflow label.
   When in doubt, OMIT rather than fabricate.

LINE-INTERNAL TOKENS vs VALVE TAGS (CRITICAL — DIN line labels embed
short `AB047`, `AH002`, `AK001`-style tokens as design-code segments;
these are NOT separate valves):

9. A short alphanumeric token of the form `A[BHKS]\d{3}` printed
   ALONG a process line — between two pieces of equipment, sharing
   the line's path, with no separate valve symbol (square + circle
   on the line) — is a LINE DESIGN CODE, not a valve. Do NOT emit it
   as equipment.

10. A real DIN valve symbol on this drawing is a small square box
    intersecting a line, OPTIONALLY with a circle bubble above it
    indicating an actuator, and bears its own dedicated tag rendered
    NEXT TO the symbol (not inline in the line text). Only emit
    equipment of type "gate_valve" / "ball_valve" / "control_valve"
    when you can clearly see such a symbol. If you only see the text
    `AB014` floating along a line, treat it as a line annotation.

11. When uncertain whether a token is a valve or a line code, prefer
    OMITTING. The downstream evaluator and self-correction loop will
    flag genuine missing valves; fabricated valves are harder to
    remove than to add later.

TITLE BLOCK / DRAWING TABLE EXCLUSION (CRITICAL):

12. The bottom-right area of DIN drawings contains a title block table
    (Zeichnungsfeld) with: drawing number (e.g. "UER-1234567"),
    revision, date, scale, company name, "CONFIDENTIAL", page numbers,
    column/row markers (A-F, 1-15), etc. These are NOT equipment,
    instruments, or lines. NEVER extract anything from the title block
    area as a process item. If you see text like "Reaktion Str.1",
    "Teil 2 (Musterfließbild)", "CDVPRL1-V999-TA99", "2020-03-18",
    these are drawing metadata, not tags.
"""


# DIN line label regex. Captures L<series>.<num>-<size>-<spec> with
# optional flow code + Z-code suffix. Examples that must match:
#   LR040.22040-80-40C1200 NF 223
#   LA01-LR024.10000-25-10H1200 NV 221
#   LR033.12000-80-10B1213 NV 221
DIN_LINE_NO_RE = re.compile(
    r'(?:(?P<prefix>L[A-Z]\d+)-)?'
    r'(?P<series>L[A-Z]{1,2}\d+)'
    r'\.(?P<num>\d+)'
    r'-(?P<size>\d+)'
    r'-(?P<spec>\d+[A-Z]\d+)'
    r'(?:\s+(?P<flow>[A-Z]{2}))?'
    r'(?:\s+(?P<zcode>\d{3}))?'
)


# DIN PSV / safety-valve pattern in service text — typically references
# the BA or KA tag the SA protects, e.g. "Sicherheitsventil zu BA101".
DIN_PSV_TARGET_RE = re.compile(
    r"\b(?:BA|KA|WA|PA|FA)\d+\b"
)


def _din_rules():
    """DIN-specific anomaly rules.

    The `vessel_without_psv_protection` rule is intentionally skipped
    on DIN drawings: SA (safety valve) symbols are smaller and harder
    for the Vision agent to ground reliably, so absence of a detected
    SA does not warrant a high-severity anomaly. orphan_instrument and
    pipe_spec_inconsistency carry over untouched.
    """
    from backend.isa_validator import (
        rule_orphan_instrument,
        rule_pipe_spec_inconsistency,
    )
    return (
        rule_orphan_instrument,
        rule_pipe_spec_inconsistency,
    )


DIN = Convention(
    name="din",
    display_name="DIN EN 10628 / DIN 19227 (Europe)",
    extractor_system_prompt=DIN_EXTRACTOR_SYSTEM,
    summary_safety_label="DIN EN 10628 룰",
    line_no_regex=DIN_LINE_NO_RE,
    service_codes_help="LR/LA/LQ + 4-digit series, NF/NV/FC/FD/FJ flow codes",
    psv_synonyms=frozenset({"safety_valve", "psv"}),
    psv_target_pattern=DIN_PSV_TARGET_RE,
    anomaly_rules=_din_rules(),
)
