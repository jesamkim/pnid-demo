"""NGL fractionation — pre-staged drawing 02 (v6, expanded).

Two-column NGL fractionation train: feed surge → deethanizer (C-201)
with overhead condenser + reflux drum + reboiler → debutanizer (C-202)
with its own condenser + reflux + reboiler → C3/C4 product drums.

Roughly 22 equipment, 28 instruments, 28 lines, 3 PSVs, 1 cascade
control loop. Canvas 6000x2200 to keep instrument bubbles separated.

Compared to v5 (11 eq / 10 inst / 13 lines): the v6 layout adds the
second column (C-202) + recycle, an extra PSV on the bottoms drum
that originally violated R1, and an FIC/PIC cascade on the
deethanizer reflux to give the demo more "control" chrome.
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
        drawing_id="02",
        title="NGL Fractionation Train (Deethanizer + Debutanizer)",
        drawing_no="PID-NGL-FRAC-002",
        canvas=(6000, 2200),
        grid_cell=160,
        equipment=[
            # ---- Feed section ----
            EqSpec("V-201",  "vessel",  col=1,  row=5, w_cells=2, h_cells=3,
                    service="NGL Feed Drum"),
            EqSpec("P-201A", "pump",    col=4,  row=5,
                    service="Feed Pump A"),
            EqSpec("P-201B", "pump",    col=4,  row=7,
                    service="Feed Pump B (spare)"),
            EqSpec("E-201",  "hx",      col=6,  row=5, w_cells=2, h_cells=2,
                    service="Feed/Bottoms Preheat"),
            # ---- Deethanizer column train (left half) ----
            EqSpec("C-201",  "column",  col=9,  row=2, w_cells=2, h_cells=8,
                    service="Deethanizer"),
            EqSpec("E-202",  "air_cooler", col=12, row=2, w_cells=3, h_cells=2,
                    service="C-201 Overhead Condenser"),
            EqSpec("V-202",  "vessel",  col=15, row=2, w_cells=2, h_cells=2,
                    service="C-201 Reflux Drum"),
            EqSpec("P-202A", "pump",    col=17, row=3,
                    service="Reflux/Distillate Pump A"),
            EqSpec("P-202B", "pump",    col=17, row=4,
                    service="Reflux/Distillate Pump B (spare)"),
            EqSpec("PSV-201","psv",     col=15, row=5,
                    service="V-202 reflux drum overpressure"),
            EqSpec("E-203",  "hx",      col=12, row=7, w_cells=2, h_cells=2,
                    service="C-201 Reboiler"),
            # ---- Inter-column transfer ----
            EqSpec("V-203",  "vessel",  col=19, row=8, w_cells=2, h_cells=2,
                    service="Deethanizer Bottoms Surge"),
            EqSpec("PSV-203","psv",     col=21, row=8,
                    service="V-203 surge drum overpressure"),
            EqSpec("P-203A", "pump",    col=22, row=9,
                    service="Bottoms Transfer Pump A"),
            # ---- Debutanizer column train (right half) ----
            EqSpec("C-202",  "column",  col=25, row=2, w_cells=2, h_cells=8,
                    service="Debutanizer"),
            EqSpec("E-204",  "air_cooler", col=28, row=2, w_cells=3, h_cells=2,
                    service="C-202 Overhead Condenser"),
            EqSpec("V-204",  "vessel",  col=31, row=2, w_cells=2, h_cells=2,
                    service="C-202 Reflux Drum"),
            EqSpec("P-204A", "pump",    col=33, row=3,
                    service="C3 Product / Reflux Pump"),
            EqSpec("PSV-204","psv",     col=31, row=5,
                    service="V-204 reflux drum overpressure"),
            EqSpec("E-205",  "hx",      col=28, row=7, w_cells=2, h_cells=2,
                    service="C-202 Reboiler"),
            EqSpec("V-205",  "vessel",  col=31, row=8, w_cells=2, h_cells=2,
                    service="C4 Bottom Product Drum"),
            EqSpec("P-205A", "pump",    col=33, row=9,
                    service="C4 Product Pump"),
        ],
        instruments=[
            # ---- Feed section ----
            InstSpec("LT-201", "LT", "201", host="V-201",  side="left"),
            InstSpec("LIC-201","LIC","201", host="V-201",  side="right"),
            InstSpec("FT-201", "FT", "201", host="P-201A", side="top"),
            InstSpec("PT-202", "PT", "202", host="P-201A", side="right"),
            InstSpec("TT-203", "TT", "203", host="E-201",  side="top"),
            InstSpec("TIC-203","TIC","203", host="E-201",  side="bottom"),
            # ---- Deethanizer (with cascade FIC-PIC) ----
            InstSpec("PT-204", "PT", "204", host="C-201",  side="left"),
            InstSpec("PIC-204","PIC","204", host="C-201",  side="right"),
            InstSpec("TT-205", "TT", "205", host="C-201",  side="left"),
            InstSpec("TT-206", "TT", "206", host="C-201",  side="right"),
            InstSpec("LT-207", "LT", "207", host="V-202",  side="top"),
            InstSpec("LIC-207","LIC","207", host="V-202",  side="bottom"),
            InstSpec("FT-208", "FT", "208", host="P-202A", side="top"),
            InstSpec("FIC-208","FIC","208", host="P-202A", side="right"),
            InstSpec("TT-209", "TT", "209", host="E-203",  side="bottom"),
            # ---- Inter-column ----
            InstSpec("LT-210", "LT", "210", host="V-203",  side="left"),
            InstSpec("FT-211", "FT", "211", host="P-203A", side="top"),
            # ---- Debutanizer ----
            InstSpec("PT-212", "PT", "212", host="C-202",  side="left"),
            InstSpec("PIC-212","PIC","212", host="C-202",  side="right"),
            InstSpec("TT-213", "TT", "213", host="C-202",  side="left"),
            InstSpec("TT-214", "TT", "214", host="C-202",  side="right"),
            InstSpec("LT-215", "LT", "215", host="V-204",  side="top"),
            InstSpec("FT-216", "FT", "216", host="P-204A", side="top"),
            InstSpec("FIC-216","FIC","216", host="P-204A", side="right"),
            InstSpec("TT-217", "TT", "217", host="E-205",  side="bottom"),
            InstSpec("TIC-217","TIC","217", host="E-205",  side="top"),
            InstSpec("LT-218", "LT", "218", host="V-205",  side="left"),
            InstSpec("LIC-218","LIC","218", host="V-205",  side="right"),
        ],
        lines=[
            # ---- Feed ----
            LineSpec('8"-NGL-201-CS',  from_ref="V-201.bottom",   to_ref="P-201A.suction",
                      size='8"',  service="NGL", spec="CS"),
            LineSpec('8"-NGL-202-CS',  from_ref="V-201.bottom",   to_ref="P-201B.suction",
                      size='8"',  service="NGL", spec="CS"),
            LineSpec('6"-NGL-203-CS',  from_ref="P-201A.discharge", to_ref="E-201.tube_in",
                      size='6"',  service="NGL", spec="CS"),
            LineSpec('6"-NGL-204-CS',  from_ref="P-201B.discharge", to_ref="E-201.tube_in",
                      size='6"',  service="NGL", spec="CS"),
            LineSpec('6"-NGL-205-CS',  from_ref="E-201.tube_out",  to_ref="C-201.feed",
                      size='6"',  service="NGL", spec="CS"),
            # ---- Deethanizer overhead ----
            LineSpec('12"-OVH-206-CS', from_ref="C-201.top",      to_ref="E-202.in",
                      size='12"', service="OVH", spec="CS"),
            LineSpec('12"-OVH-207-CS', from_ref="E-202.out",      to_ref="V-202.top",
                      size='12"', service="OVH", spec="CS"),
            LineSpec('4"-RFX-208-CS',  from_ref="V-202.bottom",   to_ref="P-202A.suction",
                      size='4"',  service="RFX", spec="CS"),
            LineSpec('4"-RFX-209-CS',  from_ref="V-202.bottom",   to_ref="P-202B.suction",
                      size='4"',  service="RFX", spec="CS"),
            LineSpec('3"-RFX-210-CS',  from_ref="P-202A.discharge", to_ref="C-201.reflux",
                      size='3"',  service="RFX", spec="CS"),
            LineSpec('4"-PSV-211-CS',  from_ref="V-202.right",    to_ref="PSV-201.in",
                      size='4"',  service="PSV", spec="CS"),
            # ---- Deethanizer reboiler ----
            LineSpec('8"-RBO-212-CS',  from_ref="C-201.reboiler_out", to_ref="E-203.shell_in",
                      size='8"',  service="RBO", spec="CS"),
            LineSpec('10"-RBO-213-CS', from_ref="E-203.shell_out", to_ref="C-201.reboiler_in",
                      size='10"', service="RBO", spec="CS"),
            # ---- Inter-column ----
            LineSpec('6"-BTM-214-CS',  from_ref="C-201.bottom",   to_ref="V-203.top",
                      size='6"',  service="BTM", spec="CS"),
            LineSpec('4"-PSV-215-CS',  from_ref="V-203.right",    to_ref="PSV-203.in",
                      size='4"',  service="PSV", spec="CS"),
            LineSpec('6"-BTM-216-CS',  from_ref="V-203.bottom",   to_ref="P-203A.suction",
                      size='6"',  service="BTM", spec="CS"),
            LineSpec('6"-FED-217-CS',  from_ref="P-203A.discharge", to_ref="C-202.feed",
                      size='6"',  service="FED", spec="CS"),
            # ---- Debutanizer overhead ----
            LineSpec('12"-OVH-218-CS', from_ref="C-202.top",      to_ref="E-204.in",
                      size='12"', service="OVH", spec="CS"),
            LineSpec('12"-OVH-219-CS', from_ref="E-204.out",      to_ref="V-204.top",
                      size='12"', service="OVH", spec="CS"),
            LineSpec('4"-RFX-220-CS',  from_ref="V-204.bottom",   to_ref="P-204A.suction",
                      size='4"',  service="RFX", spec="CS"),
            LineSpec('3"-RFX-221-CS',  from_ref="P-204A.discharge", to_ref="C-202.reflux",
                      size='3"',  service="RFX", spec="CS"),
            LineSpec('4"-PSV-222-CS',  from_ref="V-204.right",    to_ref="PSV-204.in",
                      size='4"',  service="PSV", spec="CS"),
            LineSpec('4"-C3P-223-CS',  from_ref="P-204A.discharge", to_ref="V-204.top",
                      size='4"',  service="C3P", spec="CS"),  # product to storage (loops back)
            # ---- Debutanizer reboiler ----
            LineSpec('8"-RBO-224-CS',  from_ref="C-202.reboiler_out", to_ref="E-205.shell_in",
                      size='8"',  service="RBO", spec="CS"),
            LineSpec('10"-RBO-225-CS', from_ref="E-205.shell_out", to_ref="C-202.reboiler_in",
                      size='10"', service="RBO", spec="CS"),
            # ---- C4 product ----
            LineSpec('6"-BTM-226-CS',  from_ref="C-202.bottom",   to_ref="V-205.top",
                      size='6"',  service="BTM", spec="CS"),
            LineSpec('4"-C4P-227-CS',  from_ref="V-205.bottom",   to_ref="P-205A.suction",
                      size='4"',  service="C4P", spec="CS"),
            LineSpec('4"-C4P-228-CS',  from_ref="P-205A.discharge", to_ref="V-205.top",
                      size='4"',  service="C4P", spec="CS"),  # to storage (loops back)
        ],
        anomalies=[
            AnomalySpec(
                rule="vessel_without_psv_protection", severity="medium",
                violated_by="V-205",
                description="C4 product drum V-205 has no dedicated PSV in this excerpt.",
                suggestion="Verify PSV-205 routing or add a relief tag.",
            ),
            AnomalySpec(
                rule="orphan_instrument", severity="low",
                violated_by="LT-210",
                description="LT-210 on V-203 has no controller pairing in this excerpt.",
                suggestion="Verify LIC-210 placement or add an explicit control loop.",
            ),
        ],
    )
