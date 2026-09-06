"""Crude unit obscured variant — same topology, mask painted post-render.

Returns the base TopologySpec from `topo_crude_unit` along with a
post-render hook that draws an opaque rectangle over the PSV-101 +
P-101A discharge area. Self-correction loop will recover PSV-101 in
one iteration on this drawing.
"""
from __future__ import annotations

from data.synthesis.auto_layout import (
    AnomalySpec,
    TopologySpec,
)
from data.synthesis.topo_crude_unit import build as build_main


def build() -> TopologySpec:
    base = build_main()
    # Override only the bookkeeping; geometry stays identical so the
    # ground truth lists every tag (LLM is expected to recover them).
    return TopologySpec(
        drawing_id="01b",
        title="Crude Charge and Feed Section (occluded)",
        drawing_no="PID-CRUDE-FEED-001-OBS",
        canvas=base.canvas,
        grid_cell=base.grid_cell,
        equipment=base.equipment,
        instruments=base.instruments,
        lines=base.lines,
        anomalies=tuple(base.anomalies) + (
            AnomalySpec(
                rule="occluded_region_recovered", severity="low",
                violated_by="PSV-101",
                description=(
                    "Black mask near P-101A discharge initially hid PSV-101; "
                    "self-correction loop recovered it after one iteration."
                ),
                suggestion="Original masked region resolved automatically.",
            ),
        ),
        project=base.project,
    )


def mask_overlay_svg() -> str:
    """Black rectangle covering PSV-101 (top of V-101).

    Coordinates correspond to the auto-layout grid for crude unit:
    PSV-101 sits at (col=18, row=0) with cell=160 → mask spans
    x=2880..3200, y=0..240.
    """
    return (
        '<rect x="2880" y="0" width="320" height="240" '
        'fill="#0a0a0a" stroke="#0a0a0a" />\n'
        '<text x="3040" y="130" text-anchor="middle" '
        'font-family="Helvetica" font-size="18" fill="#444">'
        '— masked region —</text>'
    )
