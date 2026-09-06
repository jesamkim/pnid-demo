"""ISA-5.1 rule-based validator.

Each rule walks the structured ExtractionResult and emits Anomaly tuples.
Rules implemented:
  R1) vessel_without_psv_protection — every pressure vessel must have a PSV
      whose `service` or a Connection.from_tag/to_tag links it to that vessel.
  R2) orphan_instrument — every instrument must connect (signal Connection,
      located_on equipment, or located_on a known line) to something.
  R3) pipe_spec_inconsistency — if the same line_no prefix (size+service+number)
      appears with multiple `spec` values, flag.
"""
from __future__ import annotations

import re

from backend.schemas import Anomaly, Connection, ExtractionResult


_PSV_PROTECTS_PATTERN = re.compile(r"\bV-\d+\b|\bT-\d+\b")
_LINE_PREFIX_RE = re.compile(r'^([0-9]+(?:/[0-9]+)?)"-([A-Z]+)-([0-9]+)')


def _vessels(r: ExtractionResult) -> list:
    # Atmospheric tanks (`tank`) are not required to carry a PSV — they
    # vent through an open vent. Pressure vessels and columns/reactors
    # are kept under the rule.
    return [e for e in r.equipment if e.type in {"vessel", "column", "reactor"}]


def _psvs(r: ExtractionResult) -> list:
    return [e for e in r.equipment if e.type == "psv"]


def _psv_protects(psv, r: ExtractionResult) -> set[str]:
    targets: set[str] = set()
    if psv.properties.get("protects"):
        targets.add(psv.properties["protects"])
    if psv.service:
        for m in _PSV_PROTECTS_PATTERN.findall(psv.service):
            targets.add(m)
    for c in r.connections:
        if c.from_tag == psv.tag:
            targets.add(c.to_tag)
        if c.to_tag == psv.tag:
            targets.add(c.from_tag)
    return targets


def rule_vessel_without_psv(r: ExtractionResult) -> tuple[Anomaly, ...]:
    vessels = _vessels(r)
    if not vessels:
        return ()
    psvs = _psvs(r)
    protected: set[str] = set()
    for psv in psvs:
        protected |= _psv_protects(psv, r)
    out: list[Anomaly] = []
    for v in vessels:
        if v.tag in protected:
            continue
        out.append(Anomaly(
            rule="vessel_without_psv_protection",
            severity="high",
            violated_by=v.tag,
            description=f"Pressure-containing equipment {v.tag} has no PSV connection in the drawing",
            suggestion="Verify PSV exists upstream/at top of vessel or check if drawing region is occluded",
        ))
    return tuple(out)


def _instrument_is_connected(inst, r: ExtractionResult) -> bool:
    if inst.located_on and inst.located_on.upper() not in {"", "UNKNOWN", "PANEL"}:
        return True
    # connected via signal connection
    for c in r.connections:
        if c.type == "signal" and (c.from_tag == inst.tag or c.to_tag == inst.tag):
            return True
    # located on a known line
    if inst.located_on:
        for l in r.lines:
            if inst.located_on == l.line_no:
                return True
    # located_on names the panel (control room) — accept as connected
    if inst.located_on and inst.located_on.lower() == "panel":
        return True
    return False


def rule_orphan_instrument(r: ExtractionResult) -> tuple[Anomaly, ...]:
    out: list[Anomaly] = []
    for inst in r.instruments:
        connected = (
            inst.located_on and inst.located_on.lower() == "panel"
        ) or _instrument_is_connected(inst, r)
        if not connected:
            out.append(Anomaly(
                rule="orphan_instrument",
                severity="medium",
                violated_by=inst.tag,
                description=f"Instrument {inst.tag} has no signal line, no panel assignment, and is not located on a known line/equipment",
                suggestion="Trace signal line on the drawing or confirm tag is mistakenly placed",
            ))
    return tuple(out)


def _line_key(line_no: str) -> str | None:
    m = _LINE_PREFIX_RE.match(line_no)
    if not m:
        return None
    return f'{m.group(1)}"-{m.group(2)}-{m.group(3)}'


def rule_pipe_spec_inconsistency(r: ExtractionResult) -> tuple[Anomaly, ...]:
    by_key: dict[str, set[str]] = {}
    for l in r.lines:
        key = _line_key(l.line_no)
        if not key or not l.spec:
            continue
        by_key.setdefault(key, set()).add(l.spec)
    # Also detect via labels stored as separate Line entries that share prefix:
    #   "8"-FD-301-CS" and "8"-FD-301-SS" share prefix '8"-FD-301' but differ in trailing token
    # Detected when two Line objects produced — already handled.
    out: list[Anomaly] = []
    for key, specs in by_key.items():
        if len(specs) > 1:
            out.append(Anomaly(
                rule="pipe_spec_inconsistency",
                severity="medium",
                violated_by=key,
                description=f"Line {key} carries inconsistent specs {sorted(specs)}",
                suggestion="One of the labels is wrong; check pipe class break conditions",
            ))

    # Cross-check by raw line_no segments: if "X-Y-Z-CS" and "X-Y-Z-SS" co-exist as line_no
    # not normalized into spec field, they appear as DIFFERENT line_no but identical key.
    by_raw_prefix: dict[str, set[str]] = {}
    for l in r.lines:
        key = _line_key(l.line_no)
        if not key:
            continue
        suffix = l.line_no[len(key):]  # e.g. "-CS" or "-SS"
        if suffix:
            by_raw_prefix.setdefault(key, set()).add(suffix)
    for key, suffixes in by_raw_prefix.items():
        if len(suffixes) > 1 and not any(a.violated_by == key for a in out):
            out.append(Anomaly(
                rule="pipe_spec_inconsistency",
                severity="medium",
                violated_by=key,
                description=f"Line {key} appears with conflicting spec suffixes {sorted(suffixes)}",
                suggestion="Reconcile labels on the drawing",
            ))
    return tuple(out)


RULES = (rule_vessel_without_psv, rule_orphan_instrument, rule_pipe_spec_inconsistency)


def validate(r: ExtractionResult, rules=None) -> tuple[Anomaly, ...]:
    """Run rule-based ISA-5.1 (or convention-specific) checks.

    `rules` defaults to the full ISA rule set so legacy callers and
    tests are unaffected. The orchestrator passes the active
    `Convention.anomaly_rules` tuple, which may drop rules that don't
    apply to that drawing's standard (e.g. DIN drops
    `vessel_without_psv_protection` because SA symbols are harder to
    ground reliably).
    """
    chosen = tuple(rules) if rules else RULES
    out: list[Anomaly] = []
    for rule in chosen:
        out.extend(rule(r))
    return tuple(out)
