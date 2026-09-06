"""Two-stage gas compressor station — pre-staged drawing 03 (v6, expanded).

Two-stage centrifugal compression with suction KO, inter-stage cooler
+ KO, after-cooler + discharge KO, anti-surge recycle loop, FT/PIC
cascade on the recycle valve. Roughly 17 equipment, 22 instruments,
22 lines, 3 PSVs.

Compared to v5 (7 eq / 8 inst / 6 lines): adds the second stage
(K-302) + interstage cooler (E-302) + interstage KO (V-302), an
anti-surge recycle path, and a flare header that the catchpot finally
vents to (which closes the v5 R1 anomaly cleanly).
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
        drawing_id="03",
        title="Two-stage Gas Compressor Station",
        drawing_no="PID-CMPR-STN-003",
        canvas=(5200, 2000),
        grid_cell=160,
        equipment=[
            # ---- Stage 1 ----
            EqSpec("V-301",  "vessel",  col=1,  row=3, w_cells=2, h_cells=4,
                    service="Stage-1 Suction KO Drum"),
            EqSpec("PSV-301","psv",     col=1,  row=1,
                    service="V-301 suction KO drum relief"),
            EqSpec("K-301",  "pump",    col=5,  row=4,
                    service="Stage-1 Centrifugal Compressor"),
            EqSpec("E-301",  "air_cooler", col=8,  row=3, w_cells=3, h_cells=2,
                    service="Stage-1 After-cooler"),
            EqSpec("V-302",  "vessel",  col=12, row=3, w_cells=2, h_cells=4,
                    service="Inter-stage KO Drum"),
            EqSpec("PSV-302","psv",     col=12, row=1,
                    service="V-302 interstage KO relief"),
            # ---- Stage 2 ----
            EqSpec("K-302",  "pump",    col=16, row=4,
                    service="Stage-2 Centrifugal Compressor"),
            EqSpec("E-302",  "air_cooler", col=19, row=3, w_cells=3, h_cells=2,
                    service="Stage-2 After-cooler"),
            EqSpec("V-303",  "vessel",  col=23, row=3, w_cells=2, h_cells=4,
                    service="Discharge KO Drum"),
            EqSpec("PSV-303","psv",     col=23, row=1,
                    service="V-303 discharge KO relief"),
            # ---- Anti-surge recycle ----
            EqSpec("CV-301", "vessel",  col=18, row=7, w_cells=1, h_cells=1,
                    service="Anti-surge recycle valve"),
            EqSpec("V-304",  "vessel",  col=25, row=7, w_cells=2, h_cells=2,
                    service="Liquids Catchpot"),
            # ---- Flare header (closes the v5 anomaly) ----
            EqSpec("FH-301", "vessel",  col=27, row=2, w_cells=2, h_cells=6,
                    service="Flare Header"),
        ],
        instruments=[
            # ---- Stage 1 ----
            InstSpec("LT-301", "LT", "301", host="V-301", side="left"),
            InstSpec("LIC-301","LIC","301", host="V-301", side="right"),
            InstSpec("PT-302", "PT", "302", host="V-301", side="right"),
            InstSpec("FT-303", "FT", "303", host="K-301", side="top"),
            InstSpec("ST-304", "ST", "304", host="K-301", side="bottom"),
            InstSpec("PIC-303","PIC","303", host="K-301", side="left"),
            InstSpec("TT-305", "TT", "305", host="E-301", side="top"),
            # ---- Inter-stage ----
            InstSpec("PT-306", "PT", "306", host="V-302", side="left"),
            InstSpec("LT-307", "LT", "307", host="V-302", side="right"),
            InstSpec("LIC-307","LIC","307", host="V-302", side="bottom"),
            # ---- Stage 2 ----
            InstSpec("FT-308", "FT", "308", host="K-302", side="top"),
            InstSpec("ST-309", "ST", "309", host="K-302", side="bottom"),
            InstSpec("PIC-308","PIC","308", host="K-302", side="left"),
            InstSpec("TT-310", "TT", "310", host="E-302", side="top"),
            # ---- Discharge / catchpot ----
            InstSpec("PT-311", "PT", "311", host="V-303", side="left"),
            InstSpec("LT-312", "LT", "312", host="V-303", side="right"),
            InstSpec("LT-313", "LT", "313", host="V-304", side="right"),
            # ---- Anti-surge cascade ----
            InstSpec("FT-314", "FT", "314", host="K-301", side="right"),
            InstSpec("FIC-314","FIC","314", host="CV-301", side="top"),
            # ---- Flare ----
            InstSpec("PT-315", "PT", "315", host="FH-301", side="left"),
            InstSpec("FT-316", "FT", "316", host="FH-301", side="right"),
        ],
        lines=[
            # ---- Stage 1 path ----
            LineSpec('20"-FG-301-CS', from_ref="V-301.bottom",   to_ref="K-301.suction",
                      size='20"', service="FG", spec="CS"),
            LineSpec('16"-FG-302-CS', from_ref="K-301.discharge", to_ref="E-301.in",
                      size='16"', service="FG", spec="CS"),
            LineSpec('16"-FG-303-CS', from_ref="E-301.out",      to_ref="V-302.top",
                      size='16"', service="FG", spec="CS"),
            LineSpec('4"-PSV-304-CS', from_ref="V-301.top",      to_ref="PSV-301.in",
                      size='4"',  service="PSV", spec="CS"),
            # ---- Inter-stage to stage 2 ----
            LineSpec('14"-FG-305-CS', from_ref="V-302.bottom",   to_ref="K-302.suction",
                      size='14"', service="FG", spec="CS"),
            LineSpec('4"-PSV-306-CS', from_ref="V-302.top",      to_ref="PSV-302.in",
                      size='4"',  service="PSV", spec="CS"),
            # ---- Stage 2 path ----
            LineSpec('12"-FG-307-CS', from_ref="K-302.discharge", to_ref="E-302.in",
                      size='12"', service="FG", spec="CS"),
            LineSpec('12"-FG-308-CS', from_ref="E-302.out",      to_ref="V-303.top",
                      size='12"', service="FG", spec="CS"),
            LineSpec('6"-PSV-309-CS', from_ref="V-303.top",      to_ref="PSV-303.in",
                      size='6"',  service="PSV", spec="CS"),
            # ---- Catchpot drain ----
            LineSpec('3"-DRN-310-CS', from_ref="V-303.bottom",   to_ref="V-304.top",
                      size='3"',  service="DRN", spec="CS"),
            # ---- Anti-surge recycle ----
            LineSpec('8"-RCY-311-CS', from_ref="V-303.bottom",   to_ref="CV-301.top",
                      size='8"',  service="RCY", spec="CS"),
            LineSpec('8"-RCY-312-CS', from_ref="CV-301.left",    to_ref="V-301.top",
                      size='8"',  service="RCY", spec="CS"),
            # ---- Flare routing (closes v5 anomaly) ----
            LineSpec('4"-FLR-313-CS', from_ref="V-304.top",      to_ref="FH-301.bottom",
                      size='4"',  service="FLR", spec="CS"),
        ],
        anomalies=[
            AnomalySpec(
                rule="orphan_instrument", severity="medium",
                violated_by="ST-304",
                description="Speed transmitter ST-304 on K-301 has no controller pairing in this excerpt.",
                suggestion="Verify SIC-304 placement — typical for compressor speed control.",
            ),
            AnomalySpec(
                rule="pipe_spec_inconsistency", severity="low",
                violated_by="14\"-FG-305-CS",
                description="Inter-stage line 14\" departs from upstream 16\" header — verify size step is by design.",
                suggestion="Confirm reducer placement on the V-302 outlet vs upstream after-cooler return.",
            ),
        ],
    )
