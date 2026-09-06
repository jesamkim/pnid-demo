"""Convention registry — maps a logical name to a Convention bundle.

A Convention captures everything the agents need to know to read a P&ID
in a particular standard family (ISA-5.1 / DIN-EN). It is passed
explicitly through the orchestrator so agent calls stay deterministic
and ralph-loop-friendly.
"""
from __future__ import annotations

from backend.agents.conventions.base import Convention
from backend.agents.conventions.isa import ISA
from backend.agents.conventions.din import DIN

CONVENTIONS: dict[str, Convention] = {
    "isa": ISA,
    "din": DIN,
}

DEFAULT = ISA

__all__ = ["Convention", "ISA", "DIN", "CONVENTIONS", "DEFAULT"]
