"""Amine treating contactor + regenerator — pre-staged drawing 04 (v6, expanded).

Sweet-gas plant excerpt: contactor (high-pressure absorber), flash
drum, regenerator (stripping column), reflux drum, lean/rich amine
heat exchanger, lean amine cooler, lean amine surge tank, mechanical
filter on lean amine, makeup water injection.

Compared to v5 (10 eq / 10 inst / 13 lines): adds the lean amine
surge tank (V-403), an inline mechanical filter (F-401), a makeup
water tie-in, an additional PSV on the flash drum (closes the v5 R1
anomaly), and instrument controllers for level and flow.
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
        drawing_id="04",
        title="Amine Treater - Contactor + Regenerator + Surge",
        drawing_no="PID-AMINE-TRT-004",
        canvas=(4400, 2000),
        grid_cell=160,
        equipment=[
            # ---- Absorber side ----
            EqSpec("C-401", "column",  col=1,  row=1, w_cells=2, h_cells=8,
                    service="Amine Contactor (Absorber)"),
            EqSpec("V-401", "vessel",  col=4,  row=4, w_cells=2, h_cells=2,
                    service="Rich Amine Flash Drum"),
            EqSpec("PSV-401","psv",    col=4,  row=2,
                    service="V-401 flash drum relief"),
            # ---- Lean/Rich exchange + Regenerator ----
            EqSpec("E-401", "hx",      col=7,  row=4, w_cells=2, h_cells=2,
                    service="Lean/Rich Amine HX"),
            EqSpec("C-402", "column",  col=10, row=1, w_cells=2, h_cells=8,
                    service="Amine Regenerator"),
            EqSpec("E-402", "air_cooler", col=13, row=1, w_cells=3, h_cells=2,
                    service="Reg Overhead Condenser"),
            EqSpec("V-402", "vessel",  col=16, row=1, w_cells=2, h_cells=2,
                    service="Reg Reflux Drum"),
            EqSpec("PSV-402","psv",    col=16, row=4,
                    service="V-402 reflux drum relief"),
            EqSpec("E-403", "hx",      col=13, row=6, w_cells=2, h_cells=2,
                    service="Reboiler (steam)"),
            # ---- Lean amine return loop ----
            EqSpec("V-403", "vessel",  col=10, row=10, w_cells=2, h_cells=2,
                    service="Lean Amine Surge Tank"),
            EqSpec("PSV-403","psv",    col=12, row=10,
                    service="V-403 surge tank relief"),
            EqSpec("F-401", "vessel",  col=7,  row=10, w_cells=2, h_cells=1,
                    service="Mechanical Filter (lean amine)"),
            EqSpec("P-401A","pump",    col=5,  row=10,
                    service="Lean Amine Circulation Pump A"),
            EqSpec("P-401B","pump",    col=5,  row=11,
                    service="Lean Amine Circulation Pump B (spare)"),
            EqSpec("E-404", "hx",      col=2,  row=10, w_cells=2, h_cells=1,
                    service="Lean Amine Cooler"),
        ],
        instruments=[
            InstSpec("PT-401", "PT", "401", host="C-401", side="left"),
            InstSpec("LT-402", "LT", "402", host="C-401", side="right"),
            InstSpec("LIC-402","LIC","402", host="C-401", side="bottom"),
            InstSpec("LT-403", "LT", "403", host="V-401", side="top"),
            InstSpec("LIC-403","LIC","403", host="V-401", side="bottom"),
            InstSpec("TT-404", "TT", "404", host="E-401", side="top"),
            InstSpec("TT-405", "TT", "405", host="C-402", side="right"),
            InstSpec("PT-406", "PT", "406", host="C-402", side="left"),
            InstSpec("PIC-406","PIC","406", host="C-402", side="bottom"),
            InstSpec("LT-407", "LT", "407", host="V-402", side="top"),
            InstSpec("TT-408", "TT", "408", host="E-403", side="bottom"),
            InstSpec("TIC-408","TIC","408", host="E-403", side="top"),
            InstSpec("LT-409", "LT", "409", host="V-403", side="left"),
            InstSpec("LIC-409","LIC","409", host="V-403", side="right"),
            InstSpec("FT-410", "FT", "410", host="P-401A", side="top"),
            InstSpec("FIC-410","FIC","410", host="P-401A", side="right"),
            InstSpec("PT-411", "PT", "411", host="F-401", side="top"),  # filter dP
            InstSpec("TT-412", "TT", "412", host="E-404", side="top"),
        ],
        lines=[
            # ---- Sweet gas overhead ----
            LineSpec('14"-FG-401-CS',  from_ref="C-401.top",      to_ref="C-401.feed",
                      size='14"', service="FG", spec="CS"),
            # ---- Rich amine path ----
            LineSpec('8"-RAM-402-CS',  from_ref="C-401.bottom",   to_ref="V-401.top",
                      size='8"',  service="RAM", spec="CS"),
            LineSpec('4"-PSV-403-CS',  from_ref="V-401.right",    to_ref="PSV-401.in",
                      size='4"',  service="PSV", spec="CS"),
            LineSpec('8"-RAM-404-CS',  from_ref="V-401.bottom",   to_ref="E-401.tube_in",
                      size='8"',  service="RAM", spec="CS"),
            LineSpec('8"-RAM-405-CS',  from_ref="E-401.tube_out", to_ref="C-402.feed",
                      size='8"',  service="RAM", spec="CS"),
            # ---- Regenerator overhead ----
            LineSpec('12"-OVH-406-CS', from_ref="C-402.top",      to_ref="E-402.in",
                      size='12"', service="OVH", spec="CS"),
            LineSpec('12"-OVH-407-CS', from_ref="E-402.out",      to_ref="V-402.top",
                      size='12"', service="OVH", spec="CS"),
            LineSpec('4"-PSV-408-CS',  from_ref="V-402.right",    to_ref="PSV-402.in",
                      size='4"',  service="PSV", spec="CS"),
            # ---- Reboiler ----
            LineSpec('10"-RBO-409-CS', from_ref="C-402.reboiler_out", to_ref="E-403.shell_in",
                      size='10"', service="RBO", spec="CS"),
            LineSpec('10"-RBO-410-CS', from_ref="E-403.shell_out", to_ref="C-402.reboiler_in",
                      size='10"', service="RBO", spec="CS"),
            # ---- Lean amine return ----
            LineSpec('8"-LAM-411-CS',  from_ref="C-402.bottom",   to_ref="E-401.shell_in",
                      size='8"',  service="LAM", spec="CS"),
            LineSpec('8"-LAM-412-CS',  from_ref="E-401.shell_out", to_ref="V-403.top",
                      size='8"',  service="LAM", spec="CS"),
            LineSpec('4"-PSV-413-CS',  from_ref="V-403.right",    to_ref="PSV-403.in",
                      size='4"',  service="PSV", spec="CS"),
            LineSpec('8"-LAM-414-CS',  from_ref="V-403.bottom",   to_ref="F-401.left",
                      size='8"',  service="LAM", spec="CS"),
            LineSpec('8"-LAM-415-CS',  from_ref="F-401.right",    to_ref="P-401A.suction",
                      size='8"',  service="LAM", spec="CS"),
            LineSpec('8"-LAM-416-CS',  from_ref="F-401.right",    to_ref="P-401B.suction",
                      size='8"',  service="LAM", spec="CS"),
            LineSpec('6"-LAM-417-CS',  from_ref="P-401A.discharge", to_ref="E-404.tube_in",
                      size='6"',  service="LAM", spec="CS"),
            LineSpec('6"-LAM-418-CS',  from_ref="P-401B.discharge", to_ref="E-404.tube_in",
                      size='6"',  service="LAM", spec="CS"),
            LineSpec('6"-LAM-419-CS',  from_ref="E-404.tube_out", to_ref="C-401.reflux",
                      size='6"',  service="LAM", spec="CS"),
            # ---- Makeup water tie-in ----
            LineSpec('2"-MUW-420-CS',  from_ref="V-403.top",      to_ref="V-403.right",
                      size='2"',  service="MUW", spec="CS"),
        ],
        anomalies=[
            AnomalySpec(
                rule="orphan_instrument", severity="low",
                violated_by="PT-411",
                description="Filter differential pressure transmitter PT-411 has no controller — operator alarm only.",
                suggestion="Confirm DCS alarm wiring on PT-411 dP high.",
            ),
        ],
    )
