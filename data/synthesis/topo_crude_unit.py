"""Crude unit feed section — hero drawing topology.

Layout reads left-to-right on a 20x10 grid (cell=160 px → 3200x1600
canvas). The process bus runs through row 5, with column C-101 acting
as the visual anchor at column 12. Reflux loop wraps over the top and
returns through V-101; bottoms drop to V-102 below the column.

Auto-routing sorts lines longest-first, so the long utility headers
(steam to F-101, CW to E-102) get first crack at the grid; short
branches snake around them.
"""
from __future__ import annotations

from data.synthesis.auto_layout import (
    AnomalySpec,
    EqSpec,
    InstSpec,
    LineSpec,
    TopologySpec,
)


def build() -> TopologySpec:
    return TopologySpec(
        drawing_id="01",
        title="Crude Charge and Feed Section",
        drawing_no="PID-CRUDE-FEED-001",
        canvas=(3840, 1600),
        grid_cell=160,
        equipment=[
            # Process bus (row 4-7 = process band)
            EqSpec("T-101",  "tank",    col=1,  row=3, w_cells=2, h_cells=4,
                    service="Crude Charge Tank"),
            EqSpec("P-101A", "pump",    col=4,  row=4,
                    service="Crude Charge Pump A"),
            EqSpec("P-101B", "pump",    col=4,  row=6,
                    service="Crude Charge Pump B (spare)"),
            # PSV-101 is placed directly above V-101 (the vessel it
            # protects) so the relief loop is geometrically short and
            # the auto-router has an unambiguous path. This is also
            # the standard "PSV on top of drum" visual idiom.
            EqSpec("PSV-101","psv",     col=18, row=0,
                    service="V-101 overhead drum overpressure relief"),
            # Each equipment leaves at least one free grid column to
            # the right so the auto-router has somewhere to lay the
            # connecting pipe without overlapping the next symbol.
            EqSpec("E-101",  "hx",      col=6,  row=4, w_cells=2, h_cells=2,
                    service="Crude/product preheat"),
            EqSpec("E-102",  "hx",      col=9,  row=4, w_cells=2, h_cells=2,
                    service="Crude/HVGO heat"),
            EqSpec("F-101",  "furnace", col=12, row=3, w_cells=2, h_cells=4,
                    service="Crude charge heater"),
            EqSpec("C-101",  "column",  col=15, row=1, w_cells=2, h_cells=8,
                    service="Atmospheric distillation tower"),
            # Top-right reflux/overhead section
            EqSpec("V-101",  "vessel",  col=18, row=1, w_cells=2, h_cells=3,
                    service="Overhead reflux drum"),
            EqSpec("P-102A", "pump",    col=21, row=2,
                    service="Reflux pump A"),
            EqSpec("P-102B", "pump",    col=21, row=4,
                    service="Reflux pump B (spare)"),
            # Bottoms surge drum (sits below column)
            EqSpec("V-102",  "vessel",  col=18, row=7, w_cells=2, h_cells=2,
                    service="Bottoms surge drum"),
        ],
        instruments=[
            # Tank + pump suction
            InstSpec("LT-101", "LT", "101", host="T-101",  side="left"),
            InstSpec("FT-101", "FT", "101", host="P-101A", side="top"),
            # Pump discharge
            InstSpec("PT-102", "PT", "102", host="P-101A", side="right"),
            # HX outlets
            InstSpec("TT-103", "TT", "103", host="E-101",  side="top"),
            InstSpec("TT-104", "TT", "104", host="E-102",  side="top"),
            # Furnace outlet
            InstSpec("TT-105", "TT", "105", host="F-101",  side="right"),
            # Column top + bottom
            InstSpec("PT-106", "PT", "106", host="C-101",  side="top"),
            InstSpec("LT-107", "LT", "107", host="C-101",  side="bottom"),
            # OVHD drum + reflux flow control
            InstSpec("LT-108", "LT", "108", host="V-101",  side="right"),
            InstSpec("FIC-109","FIC","109", host="P-102A", side="top"),
            # Bottoms drum + product flow
            InstSpec("LT-110", "LT", "110", host="V-102",  side="left"),
            InstSpec("FIC-111","FIC","111", host="V-102",  side="right"),
        ],
        lines=[
            # Process bus: T-101 → P-101 → E-101 → E-102 → F-101 → C-101
            LineSpec('12"-CRD-101-CS', from_ref="T-101.bottom",   to_ref="P-101A.suction",
                      size='12"', service="CRD", spec="CS"),
            LineSpec('12"-CRD-102-CS', from_ref="T-101.bottom",   to_ref="P-101B.suction",
                      size='12"', service="CRD", spec="CS"),
            LineSpec('8"-CRD-103-CS',  from_ref="P-101A.discharge", to_ref="E-101.tube_in",
                      size='8"',  service="CRD", spec="CS"),
            LineSpec('8"-CRD-104-CS',  from_ref="P-101B.discharge", to_ref="E-101.tube_in",
                      size='8"',  service="CRD", spec="CS"),
            LineSpec('8"-CRD-107-CS',  from_ref="E-101.tube_out",  to_ref="E-102.tube_in",
                      size='8"',  service="CRD", spec="CS"),
            LineSpec('8"-CRD-108-CS',  from_ref="E-102.tube_out",  to_ref="F-101.process_in",
                      size='8"',  service="CRD", spec="CS"),
            LineSpec('10"-CRD-109-1.25Cr', from_ref="F-101.process_out", to_ref="C-101.feed",
                      size='10"', service="CRD", spec="1.25Cr"),
            # PSV protects V-101
            LineSpec('4"-PSV-105-CS',  from_ref="V-101.top",      to_ref="PSV-101.in",
                      size='4"',  service="PSV", spec="CS"),
            # Overhead loop: C-101 top → V-101 → P-102 reflux back / product out
            LineSpec('14"-OVH-110-CS', from_ref="C-101.top",      to_ref="V-101.top",
                      size='14"', service="OVH", spec="CS"),
            LineSpec('6"-RFX-111-CS',  from_ref="V-101.bottom",   to_ref="P-102A.suction",
                      size='6"',  service="RFX", spec="CS"),
            LineSpec('6"-RFX-112-CS',  from_ref="V-101.bottom",   to_ref="P-102B.suction",
                      size='6"',  service="RFX", spec="CS"),
            LineSpec('4"-RFX-113-CS',  from_ref="P-102A.discharge", to_ref="C-101.reflux",
                      size='4"',  service="RFX", spec="CS"),
            # Bottoms: column → V-102 → product
            LineSpec('10"-AGO-115-CS', from_ref="C-101.bottom",   to_ref="V-102.top",
                      size='10"', service="AGO", spec="CS"),
        ],
        anomalies=[
            AnomalySpec(
                rule="vessel_without_psv_protection", severity="medium",
                violated_by="V-102",
                description="Bottoms surge drum V-102 has no PSV connection in this excerpt.",
                suggestion="Verify PSV-102 (not modelled here) or add a relief tag.",
            ),
            AnomalySpec(
                rule="vessel_without_psv_protection", severity="low",
                violated_by="C-101",
                description="Distillation column C-101 has no PSV connection in this excerpt.",
                suggestion="C-101 vents through V-101 / PSV-101; add explicit relief tag for clarity.",
            ),
        ],
    )
