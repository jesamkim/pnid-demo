"""Kälteerzeugung & Vakuumstation P&ID — synthetic DIN-standard drawing.

A purpose-built, high-density synthetic P&ID drawn to DIN EN 10628 /
DIN 19227 conventions (German tags + German service names), at the same
complexity tier as drawing 00. It depicts a refrigeration / cooling
plant with a vacuum station:

  - Ammoniak-Kältekreislauf (NH3 refrigeration loop): Verdichter,
    Kondensator, Sammler, Drosselventil, Verdampfer.
  - Kühlwasserkreislauf (cooling-water circuit): Pumpen, Kühlturm,
    Plattenwärmetauscher.
  - Soleverteilung (brine distribution) to consumers.
  - Vakuumstation (vacuum station): Vakuumpumpen + Abscheider.
  - Voller Instrumentenkranz (full instrument set) nach DIN 19227:
    TIR/PIR/LIR/FIR Messstellen + Regelkreise.

DIN tag scheme (mirrors the real UER-1234567 drawing so the
convention-detector classifies it as DIN, not ISA):
  - Equipment prefixes: KA (Kältemaschine/Verdichter), BA (Behälter),
    WA (Wärmetauscher), PA (Pumpe), KO (Kolonne/Turm), SA (Sicherheits-
    ventil = relief).
  - Instruments: DIN 19227 letter codes — T/P/L/F (Temperatur, Druck,
    Niveau/Level, Durchfluss/Flow) + I (Anzeige) R (Registrierung)
    C (Regelung). e.g. TIR, PIRC, LIR, FIRC.
  - Lines: "LR<sys>.<seq>-<DN>-<spec>" German line numbers.

Counts (target ≈ drawing 00): ~50 equipment, ~60 instruments,
~50 lines, with safety valves + several control loops.

Reuses the existing isa_svg symbol set — the symbols are process
equipment (vessel/pump/hx/column/...), which are standard-agnostic;
only the *tags / labels / services* differ between ISA and DIN.

Anomalies (intentional, for the rule engine):
  - vessel_without_psv_protection: NH3-Sammler BA-204 ohne SA
  - orphan_instrument: TIR-518 ohne zugehörigen Regelkreis
  - pipe_spec_inconsistency: DN200→DN150 ohne Spec-Hinweis
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
        drawing_id="02_din_kaelte",
        title="Kälteerzeugung und Vakuumstation",
        drawing_no="RI-KAE-VAK-002",
        canvas=(10000, 3800),
        grid_cell=160,
        project="ROADSHOW DEMO · DIN EN 10628",
        equipment=[
            # =================================================================
            # REIHE 1 (Zeile 1-7): NH3-KÄLTEKREISLAUF (refrigeration loop)
            # =================================================================
            EqSpec("KA-101", "pump",   col=2,  row=2,
                   service="NH3-Verdichter 1. Stufe"),
            EqSpec("KA-102", "pump",   col=2,  row=3,
                   service="NH3-Verdichter 2. Stufe"),
            EqSpec("WA-101", "hx",     col=5,  row=2, w_cells=2, h_cells=2,
                   service="Ölkühler Verdichter"),
            EqSpec("WA-102", "air_cooler", col=8, row=1, w_cells=3, h_cells=2,
                   service="NH3-Verflüssiger (Kondensator)"),
            EqSpec("BA-101", "vessel", col=12, row=2, w_cells=2, h_cells=3,
                   service="Hochdruck-Sammler"),
            EqSpec("SA-101", "psv",    col=12, row=0,
                   service="BA-101 Sicherheitsventil"),
            EqSpec("BA-102", "vessel", col=15, row=2, w_cells=2, h_cells=3,
                   service="NH3-Vorratsbehälter"),
            EqSpec("SA-102", "psv",    col=15, row=0,
                   service="BA-102 Sicherheitsventil"),
            EqSpec("WA-103", "hx",     col=18, row=2, w_cells=2, h_cells=2,
                   service="Unterkühler"),
            EqSpec("BA-103", "vessel", col=22, row=2, w_cells=2, h_cells=3,
                   service="Niederdruck-Abscheider"),
            EqSpec("SA-103", "psv",    col=22, row=0,
                   service="BA-103 Sicherheitsventil"),
            EqSpec("WA-104", "hx",     col=26, row=2, w_cells=2, h_cells=3,
                   service="NH3-Verdampfer / Sole"),
            EqSpec("BA-104", "vessel", col=30, row=2, w_cells=2, h_cells=3,
                   service="Saugabscheider"),
            EqSpec("KA-103", "pump",   col=34, row=2,
                   service="NH3-Umwälzpumpe"),

            # =================================================================
            # REIHE 2 (Zeile 8-15): KÜHLWASSER + SOLEVERTEILUNG
            # =================================================================
            EqSpec("KO-201", "column", col=3,  row=8, w_cells=2, h_cells=9,
                   service="Kühlturm (Rückkühlwerk)"),
            EqSpec("BA-201", "tank",   col=6,  row=14, w_cells=3, h_cells=2,
                   service="Kühlwasser-Vorlagebehälter"),
            EqSpec("PA-201", "pump",   col=10, row=13,
                   service="Kühlwasserpumpe 1"),
            EqSpec("PA-202", "pump",   col=10, row=14,
                   service="Kühlwasserpumpe 2 (Reserve)"),
            EqSpec("WA-201", "hx",     col=13, row=12, w_cells=2, h_cells=3,
                   service="Plattenwärmetauscher KW/Sole"),
            EqSpec("BA-202", "vessel", col=17, row=12, w_cells=2, h_cells=3,
                   service="Sole-Ausdehnungsgefäß"),
            EqSpec("SA-201", "psv",    col=17, row=10,
                   service="BA-202 Sicherheitsventil"),
            EqSpec("PA-203", "pump",   col=21, row=13,
                   service="Solepumpe 1"),
            EqSpec("PA-204", "pump",   col=21, row=14,
                   service="Solepumpe 2 (Reserve)"),
            EqSpec("BA-203", "vessel", col=24, row=12, w_cells=2, h_cells=3,
                   service="Sole-Verteiler"),
            EqSpec("WA-202", "hx",     col=28, row=12, w_cells=2, h_cells=2,
                   service="Sole-Kühler Verbraucher A"),
            EqSpec("WA-203", "hx",     col=28, row=14, w_cells=2, h_cells=2,
                   service="Sole-Kühler Verbraucher B"),
            EqSpec("BA-204", "vessel", col=32, row=12, w_cells=2, h_cells=3,
                   service="NH3-Notsammler"),  # anomaly: no SA

            # =================================================================
            # REIHE 3 (Zeile 16-22): VAKUUMSTATION + HILFSSYSTEME
            # =================================================================
            EqSpec("BA-301", "vessel", col=4,  row=17, w_cells=2, h_cells=3,
                   service="Vakuum-Vorabscheider"),
            EqSpec("KA-301", "pump",   col=8,  row=18,
                   service="Vakuumpumpe 1"),
            EqSpec("KA-302", "pump",   col=8,  row=19,
                   service="Vakuumpumpe 2"),
            EqSpec("WA-301", "hx",     col=11, row=17, w_cells=2, h_cells=2,
                   service="Zwischenkühler Vakuum"),
            EqSpec("BA-302", "vessel", col=15, row=17, w_cells=2, h_cells=3,
                   service="Kondensatabscheider"),
            EqSpec("SA-301", "psv",    col=15, row=15,
                   service="BA-302 Sicherheitsventil"),
            EqSpec("PA-301", "pump",   col=19, row=18,
                   service="Kondensatpumpe"),
            EqSpec("BA-303", "tank",   col=22, row=17, w_cells=3, h_cells=2,
                   service="Kondensat-Sammeltank"),
            EqSpec("WA-302", "air_cooler", col=27, row=16, w_cells=3, h_cells=2,
                   service="Nachkühler Vakuumabgas"),
            EqSpec("BA-304", "vessel", col=32, row=17, w_cells=2, h_cells=3,
                   service="Abgas-Abscheider"),
            EqSpec("SA-302", "psv",    col=32, row=15,
                   service="BA-304 Sicherheitsventil"),
        ],
        instruments=[
            # --- NH3-Kältekreislauf (refrigeration loop) ---
            InstSpec("PIRC-101", "PIRC", "101", host="KA-101", side="top"),
            InstSpec("TIR-102",  "TIR",  "102", host="KA-101", side="bottom"),
            InstSpec("PIR-103",  "PIR",  "103", host="KA-102", side="top"),
            InstSpec("TIR-104",  "TIR",  "104", host="WA-101", side="top"),
            InstSpec("TIRC-105", "TIRC", "105", host="WA-102", side="top"),
            InstSpec("PIR-106",  "PIR",  "106", host="BA-101", side="left"),
            InstSpec("LIRC-107", "LIRC", "107", host="BA-101", side="right"),
            InstSpec("LIR-108",  "LIR",  "108", host="BA-102", side="left"),
            InstSpec("PIRC-109", "PIRC", "109", host="BA-102", side="right"),
            InstSpec("TIR-110",  "TIR",  "110", host="WA-103", side="top"),
            InstSpec("LIRC-111", "LIRC", "111", host="BA-103", side="left"),
            InstSpec("PIR-112",  "PIR",  "112", host="BA-103", side="right"),
            InstSpec("TIRC-113", "TIRC", "113", host="WA-104", side="top"),
            InstSpec("FIR-114",  "FIR",  "114", host="WA-104", side="bottom"),
            InstSpec("LIR-115",  "LIR",  "115", host="BA-104", side="left"),
            InstSpec("PIR-116",  "PIR",  "116", host="BA-104", side="right"),
            InstSpec("FIRC-117", "FIRC", "117", host="KA-103", side="top"),
            InstSpec("PIR-118",  "PIR",  "118", host="KA-103", side="bottom"),

            # --- Kühlwasser + Sole (cooling water + brine) ---
            InstSpec("TIR-201",  "TIR",  "201", host="KO-201", side="top"),
            InstSpec("LIRC-202", "LIRC", "202", host="BA-201", side="top"),
            InstSpec("FIRC-203", "FIRC", "203", host="PA-201", side="top"),
            InstSpec("PIR-204",  "PIR",  "204", host="PA-201", side="bottom"),
            InstSpec("PIR-205",  "PIR",  "205", host="PA-202", side="top"),
            InstSpec("TIRC-206", "TIRC", "206", host="WA-201", side="top"),
            InstSpec("TIR-207",  "TIR",  "207", host="WA-201", side="bottom"),
            InstSpec("LIRC-208", "LIRC", "208", host="BA-202", side="left"),
            InstSpec("PIR-209",  "PIR",  "209", host="BA-202", side="right"),
            InstSpec("FIRC-210", "FIRC", "210", host="PA-203", side="top"),
            InstSpec("PIR-211",  "PIR",  "211", host="PA-204", side="top"),
            InstSpec("LIR-212",  "LIR",  "212", host="BA-203", side="left"),
            InstSpec("TIRC-213", "TIRC", "213", host="WA-202", side="top"),
            InstSpec("TIRC-214", "TIRC", "214", host="WA-203", side="top"),
            InstSpec("FIR-215",  "FIR",  "215", host="WA-202", side="bottom"),
            InstSpec("FIR-216",  "FIR",  "216", host="WA-203", side="bottom"),
            InstSpec("LIR-217",  "LIR",  "217", host="BA-204", side="left"),

            # --- Vakuumstation ---
            InstSpec("PIRC-301", "PIRC", "301", host="BA-301", side="left"),
            InstSpec("LIR-302",  "LIR",  "302", host="BA-301", side="right"),
            InstSpec("PIRC-303", "PIRC", "303", host="KA-301", side="top"),
            InstSpec("TIR-304",  "TIR",  "304", host="KA-301", side="bottom"),
            InstSpec("PIR-305",  "PIR",  "305", host="KA-302", side="top"),
            InstSpec("TIR-306",  "TIR",  "306", host="WA-301", side="top"),
            InstSpec("LIRC-307", "LIRC", "307", host="BA-302", side="left"),
            InstSpec("PIR-308",  "PIR",  "308", host="BA-302", side="right"),
            InstSpec("FIRC-309", "FIRC", "309", host="PA-301", side="top"),
            InstSpec("LIRC-310", "LIRC", "310", host="BA-303", side="top"),
            InstSpec("TIRC-311", "TIRC", "311", host="WA-302", side="top"),
            InstSpec("PIR-312",  "PIR",  "312", host="BA-304", side="left"),
            InstSpec("LIR-313",  "LIR",  "313", host="BA-304", side="right"),
            InstSpec("TIR-314",  "TIR",  "314", host="WA-301", side="bottom"),
            InstSpec("FIR-315",  "FIR",  "315", host="BA-303", side="bottom"),
            InstSpec("PIR-316",  "PIR",  "316", host="BA-301", side="top"),
            InstSpec("TIR-317",  "TIR",  "317", host="WA-302", side="bottom"),
            # orphan instrument (anomaly) — kein Regelkreis
            InstSpec("TIR-518",  "TIR",  "518", host="BA-204", side="right"),
        ],
        lines=[
            # --- NH3-Kältekreislauf ---
            LineSpec("LR101.10-DN150-NH3", from_ref="KA-101.discharge", to_ref="WA-101.tube_in",
                     size="DN150", service="NH3-Heißgas", spec="C22.8"),
            LineSpec("LR102.11-DN150-NH3", from_ref="WA-101.tube_out", to_ref="WA-102.in",
                     size="DN150", service="NH3-Heißgas", spec="C22.8"),
            LineSpec("LR103.12-DN200-NH3", from_ref="WA-102.out", to_ref="BA-101.top",
                     size="DN200", service="NH3-flüssig", spec="C22.8"),
            LineSpec("LR104.13-DN100-NH3", from_ref="BA-101.bottom", to_ref="BA-102.top",
                     size="DN100", service="NH3-flüssig", spec="C22.8"),
            LineSpec("LR105.14-DN80-NH3",  from_ref="BA-102.bottom", to_ref="WA-103.tube_in",
                     size="DN80", service="NH3-flüssig", spec="C22.8"),
            LineSpec("LR106.15-DN80-NH3",  from_ref="WA-103.tube_out", to_ref="BA-103.top",
                     size="DN80", service="NH3-flüssig", spec="C22.8"),
            LineSpec("LR107.16-DN150-NH3", from_ref="BA-103.bottom", to_ref="WA-104.tube_in",
                     size="DN150", service="NH3-Nassdampf", spec="C22.8"),
            LineSpec("LR108.17-DN200-NH3", from_ref="WA-104.tube_out", to_ref="BA-104.bottom",
                     size="DN200", service="NH3-Sauggas", spec="C22.8"),
            LineSpec("LR109.18-DN200-NH3", from_ref="BA-104.top", to_ref="KA-103.suction",
                     size="DN200", service="NH3-Sauggas", spec="C22.8"),
            LineSpec("LR110.19-DN200-NH3", from_ref="KA-103.discharge", to_ref="KA-101.suction",
                     size="DN200", service="NH3-Sauggas", spec="C22.8"),
            LineSpec("LR111.20-DN50-NH3",  from_ref="BA-101.top", to_ref="SA-101.in",
                     size="DN50", service="NH3-Abblasung", spec="C22.8"),
            LineSpec("LR112.21-DN50-NH3",  from_ref="BA-102.top", to_ref="SA-102.in",
                     size="DN50", service="NH3-Abblasung", spec="C22.8"),
            LineSpec("LR113.22-DN50-NH3",  from_ref="BA-103.top", to_ref="SA-103.in",
                     size="DN50", service="NH3-Abblasung", spec="C22.8"),

            # --- Kühlwasser + Sole ---
            LineSpec("LR201.30-DN300-KW", from_ref="KO-201.bottom", to_ref="BA-201.top",
                     size="DN300", service="Kühlwasser", spec="P235"),
            LineSpec("LR202.31-DN300-KW", from_ref="BA-201.bottom", to_ref="PA-201.suction",
                     size="DN300", service="Kühlwasser", spec="P235"),
            LineSpec("LR203.32-DN300-KW", from_ref="BA-201.bottom", to_ref="PA-202.suction",
                     size="DN300", service="Kühlwasser", spec="P235"),
            LineSpec("LR204.33-DN250-KW", from_ref="PA-201.discharge", to_ref="WA-201.tube_in",
                     size="DN250", service="Kühlwasser", spec="P235"),
            LineSpec("LR205.34-DN250-KW", from_ref="PA-202.discharge", to_ref="WA-201.tube_in",
                     size="DN250", service="Kühlwasser", spec="P235"),
            LineSpec("LR206.35-DN300-KW", from_ref="WA-201.tube_out", to_ref="KO-201.top",
                     size="DN300", service="Kühlwasser-Rücklauf", spec="P235"),
            LineSpec("LR207.40-DN200-SOL", from_ref="WA-201.shell_out", to_ref="BA-202.top",
                     size="DN200", service="Sole", spec="P265"),
            LineSpec("LR208.41-DN200-SOL", from_ref="BA-202.bottom", to_ref="PA-203.suction",
                     size="DN200", service="Sole", spec="P265"),
            LineSpec("LR209.42-DN200-SOL", from_ref="BA-202.bottom", to_ref="PA-204.suction",
                     size="DN200", service="Sole", spec="P265"),
            LineSpec("LR210.43-DN150-SOL", from_ref="PA-203.discharge", to_ref="BA-203.top",
                     size="DN150", service="Sole", spec="P265"),
            LineSpec("LR211.44-DN150-SOL", from_ref="PA-204.discharge", to_ref="BA-203.top",
                     size="DN150", service="Sole", spec="P265"),
            LineSpec("LR212.45-DN100-SOL", from_ref="BA-203.bottom", to_ref="WA-202.tube_in",
                     size="DN100", service="Sole-Vorlauf", spec="P265"),
            LineSpec("LR213.46-DN100-SOL", from_ref="BA-203.bottom", to_ref="WA-203.tube_in",
                     size="DN100", service="Sole-Vorlauf", spec="P265"),
            LineSpec("LR214.47-DN150-SOL", from_ref="WA-104.shell_out", to_ref="BA-203.bottom",
                     size="DN150", service="Sole-Kälte", spec="P265"),
            LineSpec("LR215.48-DN50-SOL",  from_ref="BA-202.top", to_ref="SA-201.in",
                     size="DN50", service="Sole-Abblasung", spec="P265"),

            # --- Vakuumstation ---
            LineSpec("LR301.50-DN200-VAK", from_ref="BA-301.top", to_ref="KA-301.suction",
                     size="DN200", service="Vakuum-Sauggas", spec="1.4571"),
            LineSpec("LR302.51-DN200-VAK", from_ref="BA-301.top", to_ref="KA-302.suction",
                     size="DN200", service="Vakuum-Sauggas", spec="1.4571"),
            LineSpec("LR303.52-DN150-VAK", from_ref="KA-301.discharge", to_ref="WA-301.tube_in",
                     size="DN150", service="Vakuum-Abgas", spec="1.4571"),
            LineSpec("LR304.53-DN150-VAK", from_ref="KA-302.discharge", to_ref="WA-301.tube_in",
                     size="DN150", service="Vakuum-Abgas", spec="1.4571"),
            LineSpec("LR305.54-DN150-VAK", from_ref="WA-301.tube_out", to_ref="BA-302.top",
                     size="DN150", service="Vakuum-Abgas", spec="1.4571"),
            LineSpec("LR306.55-DN80-KON",  from_ref="BA-302.bottom", to_ref="PA-301.suction",
                     size="DN80", service="Kondensat", spec="P235"),
            LineSpec("LR307.56-DN80-KON",  from_ref="PA-301.discharge", to_ref="BA-303.top",
                     size="DN80", service="Kondensat", spec="P235"),
            # spec inconsistency (anomaly): DN200 → DN150 ohne Hinweis
            LineSpec("LR308.57-DN150-VAK", from_ref="BA-302.top", to_ref="WA-302.in",
                     size="DN150", service="Abgas", spec="1.4571"),
            LineSpec("LR309.58-DN150-VAK", from_ref="WA-302.out", to_ref="BA-304.top",
                     size="DN150", service="Abgas", spec="1.4571"),
            LineSpec("LR310.59-DN50-VAK",  from_ref="BA-304.top", to_ref="SA-302.in",
                     size="DN50", service="Abgas-Abblasung", spec="1.4571"),
            LineSpec("LR311.60-DN50-VAK",  from_ref="BA-302.top", to_ref="SA-301.in",
                     size="DN50", service="Abblasung", spec="1.4571"),
        ],
        anomalies=[
            AnomalySpec(
                rule="vessel_without_psv_protection",
                severity="high",
                violated_by="BA-204",
                description="NH3-Notsammler BA-204 ohne zugeordnetes Sicherheitsventil (SA).",
                suggestion="Sicherheitsventil an BA-204 ergänzen (DIN EN 378).",
            ),
            AnomalySpec(
                rule="orphan_instrument",
                severity="medium",
                violated_by="TIR-518",
                description="Temperaturmessstelle TIR-518 ohne zugehörigen Regelkreis.",
                suggestion="Regelkreis zuordnen oder Messstelle entfernen.",
            ),
            AnomalySpec(
                rule="pipe_spec_inconsistency",
                severity="medium",
                violated_by="LR308.57-DN150-VAK",
                description="DN200 → DN150 Reduktion ohne Spec-Hinweis am Übergang.",
                suggestion="Reduzierstück + Spec-Wechsel kennzeichnen.",
            ),
        ],
    )
