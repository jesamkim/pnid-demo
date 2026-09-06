"""Synthesize Drawing 1: Three-Phase Separator P&ID.

Equipment:  V-101 (separator), P-101 A/B (pumps), E-101 (heat exchanger)
Instruments: PT-101, LT-101, LIC-101, FT-102, TIC-101
Safety:     PSV-101 (on V-101)

Produces:
  data/samples/01_separator_pid.svg
  data/samples/01_separator_pid.pdf
  data/ground_truth/01_separator_pid.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data.synthesis import isa_svg as S

OUT_DIR = Path(__file__).resolve().parent.parent.parent
SAMPLES = OUT_DIR / "data" / "samples"
GT = OUT_DIR / "data" / "ground_truth"
SAMPLES.mkdir(parents=True, exist_ok=True)
GT.mkdir(parents=True, exist_ok=True)

W, H = 2700, 1600


def build() -> tuple[str, dict]:
    parts: list[str] = []
    equipment: list[dict] = []
    instruments: list[dict] = []
    lines: list[dict] = []
    connections: list[dict] = []

    # --- Equipment ---
    v101 = S.vessel(cx=900, cy=720, w=320, h=720, tag="V-101")
    parts.append(v101.svg)
    equipment.append({"tag": "V-101", "type": "vessel",
                      "service": "Three-Phase Separator",
                      "bbox": list(v101.bbox)})

    p101a = S.pump_centrifugal(cx=1500, cy=950, r=55, tag="P-101A")
    parts.append(p101a.svg)
    equipment.append({"tag": "P-101A", "type": "pump",
                      "service": "Liquid Hydrocarbon Pump (Main)", "bbox": list(p101a.bbox)})

    p101b = S.pump_centrifugal(cx=1500, cy=1180, r=55, tag="P-101B")
    parts.append(p101b.svg)
    equipment.append({"tag": "P-101B", "type": "pump",
                      "service": "Liquid Hydrocarbon Pump (Spare)", "bbox": list(p101b.bbox)})

    e101 = S.heat_exchanger(cx=2050, cy=950, w=240, h=160, tag="E-101")
    parts.append(e101.svg)
    equipment.append({"tag": "E-101", "type": "heat_exchanger",
                      "service": "Product Cooler", "bbox": list(e101.bbox)})

    # --- Safety ---
    psv101 = S.psv(cx=900, cy=290, size=40, tag="PSV-101")
    parts.append(psv101.svg)
    equipment.append({"tag": "PSV-101", "type": "psv",
                      "service": "V-101 overpressure protection",
                      "set_pressure_barg": 22, "bbox": list(psv101.bbox),
                      "protects": "V-101"})

    # --- Block valves on pump suction/discharge ---
    gv_sa_in = S.gate_valve(cx=1320, cy=950, size=22, tag="GV-101A")
    parts.append(gv_sa_in.svg)
    equipment.append({"tag": "GV-101A", "type": "gate_valve", "bbox": list(gv_sa_in.bbox)})

    gv_sb_in = S.gate_valve(cx=1320, cy=1180, size=22, tag="GV-101B")
    parts.append(gv_sb_in.svg)
    equipment.append({"tag": "GV-101B", "type": "gate_valve", "bbox": list(gv_sb_in.bbox)})

    gv_d = S.gate_valve(cx=1700, cy=950, size=22, tag="GV-102")
    parts.append(gv_d.svg)
    equipment.append({"tag": "GV-102", "type": "gate_valve", "bbox": list(gv_d.bbox)})

    # --- Process piping ---
    # Inlet feed line top of V-101
    parts.append(S.pipe((300, 600), v101.ports["left"]))
    parts.append(S.line_label(330, 590, '6"-FG-101-CS'))
    lines.append({"line_no": '6"-FG-101-CS', "size": '6"', "service": "FG", "spec": "CS",
                  "from_tag": "INLET", "to_tag": "V-101"})

    # Vapor outlet top: V-101 -> right -> down to vent header on the right side
    parts.append(S.pipe(v101.ports["top"], (1500, 360), elbow="h"))
    parts.append(S.line_label(1100, 350, '4"-V-102-CS'))
    parts.append(f'<text x="1510" y="365" {S.TEXT_FONT}>TO VENT HEADER</text>')
    lines.append({"line_no": '4"-V-102-CS', "size": '4"', "service": "V", "spec": "CS",
                  "from_tag": "V-101", "to_tag": "VENT_HEADER"})

    # PSV inlet/outlet (from vessel top branch to PSV, then to flare on left)
    parts.append(S.pipe((900, 360), psv101.ports["in"], elbow="v"))
    parts.append(S.pipe(psv101.ports["out"], (500, 230), elbow="v"))
    parts.append(S.line_label(560, 215, '3"-PSV-103'))
    parts.append(f'<text x="370" y="230" {S.TEXT_FONT}>TO FLARE</text>')
    lines.append({"line_no": '3"-PSV-103', "size": '3"', "service": "PSV",
                  "from_tag": "PSV-101", "to_tag": "FLARE"})
    connections.append({"from_tag": "V-101", "to_tag": "PSV-101", "type": "process"})
    connections.append({"from_tag": "PSV-101", "to_tag": "FLARE", "type": "process"})

    # Liquid outlet bottom -> tee to two pumps
    parts.append(S.pipe(v101.ports["bottom"], (900, 950)))
    parts.append(S.pipe((900, 950), gv_sa_in.ports["in"]))
    parts.append(S.pipe((900, 950), (900, 1180)))
    parts.append(S.pipe((900, 1180), gv_sb_in.ports["in"]))
    parts.append(S.line_label(910, 945, '6"-HC-104-CS'))
    lines.append({"line_no": '6"-HC-104-CS', "size": '6"', "service": "HC", "spec": "CS",
                  "from_tag": "V-101", "to_tag": "P-101A/B"})
    connections.append({"from_tag": "V-101", "to_tag": "P-101A", "type": "process"})
    connections.append({"from_tag": "V-101", "to_tag": "P-101B", "type": "process"})

    # Pump A suction/discharge
    parts.append(S.pipe(gv_sa_in.ports["out"], p101a.ports["suction"]))
    parts.append(S.pipe(p101a.ports["discharge"], gv_d.ports["in"]))
    parts.append(S.pipe(gv_d.ports["out"], e101.ports["tube_in"]))
    parts.append(S.line_label(1730, 945, '4"-HC-105-CS'))
    lines.append({"line_no": '4"-HC-105-CS', "size": '4"', "service": "HC", "spec": "CS",
                  "from_tag": "P-101A", "to_tag": "E-101"})
    connections.append({"from_tag": "P-101A", "to_tag": "E-101", "type": "process"})

    # Pump B parallel discharge merging
    parts.append(S.pipe(gv_sb_in.ports["out"], p101b.ports["suction"]))
    parts.append(S.pipe(p101b.ports["discharge"], (1700, 1180), elbow="h"))
    parts.append(S.pipe((1700, 1180), (1700, 950), elbow="v"))
    connections.append({"from_tag": "P-101B", "to_tag": "E-101", "type": "process"})

    # E-101 product outlet exits to battery limit on the right
    parts.append(S.pipe(e101.ports["tube_out"], (2350, e101.ports["tube_out"][1])))
    parts.append(S.line_label(2200, e101.ports["tube_out"][1] - 8, '4"-HC-106-CS'))
    parts.append(f'<text x="2360" y="{e101.ports["tube_out"][1]+5}" {S.TEXT_FONT}>TO PRODUCT TANK (B.L.)</text>')
    lines.append({"line_no": '4"-HC-106-CS', "size": '4"', "service": "HC", "spec": "CS",
                  "from_tag": "E-101", "to_tag": "BL"})

    # Cooling water shell-side: in from below E-101 (left port), out below (right side)
    cw_in_x = e101.ports["shell_in"][0]
    cw_in_y = e101.ports["shell_in"][1]
    cw_out_x = e101.ports["shell_out"][0]
    cw_out_y = e101.ports["shell_out"][1]
    parts.append(S.pipe((cw_in_x, 1320), (cw_in_x, cw_in_y), elbow="v"))
    parts.append(S.pipe((cw_out_x, cw_out_y), (cw_out_x, 1320), elbow="v"))
    parts.append(S.line_label(cw_in_x + 8, 1300, '6"-CW-107-CS'))
    parts.append(S.line_label(cw_out_x + 8, 1300, '6"-CW-108-CS'))
    parts.append(f'<text x="{cw_in_x - 60}" y="1340" {S.TEXT_FONT}>CW SUPPLY</text>')
    parts.append(f'<text x="{cw_out_x - 60}" y="1340" {S.TEXT_FONT}>CW RETURN</text>')
    lines.append({"line_no": '6"-CW-107-CS', "size": '6"', "service": "CW", "spec": "CS",
                  "from_tag": "CW_SUPPLY", "to_tag": "E-101"})
    lines.append({"line_no": '6"-CW-108-CS', "size": '6"', "service": "CW", "spec": "CS",
                  "from_tag": "E-101", "to_tag": "CW_RETURN"})

    # --- Instruments ---
    pt = S.instrument(cx=600, cy=520, r=32, function="PT", loop="101")
    parts.append(pt.svg)
    # PT signal connects from vessel wall (left side) horizontally to bubble
    parts.append(S.signal((740, 540), (632, 540), elbow="h"))
    instruments.append({"tag": "PT-101", "function": "PT", "loop_id": "101",
                        "located_on": "V-101", "bbox": list(pt.bbox),
                        "purpose": "Pressure measurement"})

    lt = S.instrument(cx=600, cy=900, r=32, function="LT", loop="101")
    parts.append(lt.svg)
    # LT process tap from vessel side
    parts.append(S.signal((740, 900), (632, 900), elbow="h"))
    instruments.append({"tag": "LT-101", "function": "LT", "loop_id": "101",
                        "located_on": "V-101", "bbox": list(lt.bbox),
                        "purpose": "Level measurement"})

    lic = S.instrument(cx=420, cy=900, r=32, function="LIC", loop="101")
    parts.append(lic.svg)
    # LIC <- LT signal
    parts.append(S.signal((568, 900), (452, 900), elbow="h"))
    instruments.append({"tag": "LIC-101", "function": "LIC", "loop_id": "101",
                        "located_on": "panel", "bbox": list(lic.bbox),
                        "purpose": "Level indication and control"})
    connections.append({"from_tag": "LT-101", "to_tag": "LIC-101", "type": "signal"})

    ft = S.instrument(cx=1820, cy=830, r=32, function="FT", loop="102")
    parts.append(ft.svg)
    # FT taps off discharge piping
    parts.append(S.signal((1820, 862), (1820, 950)))
    instruments.append({"tag": "FT-102", "function": "FT", "loop_id": "102",
                        "located_on": '4"-HC-105-CS', "bbox": list(ft.bbox),
                        "purpose": "Discharge flow measurement"})

    tic = S.instrument(cx=2050, cy=820, r=32, function="TIC", loop="101")
    parts.append(tic.svg)
    # TIC taps off E-101 tube outlet
    parts.append(S.signal((2050, 852), (2050, 870)))
    instruments.append({"tag": "TIC-101", "function": "TIC", "loop_id": "101",
                        "located_on": "E-101 outlet", "bbox": list(tic.bbox),
                        "purpose": "Outlet temperature indicator and controller"})

    # --- Title block ---
    parts.append(S.title_block(x=W - 600 - 40, y=H - 160 - 40,
                               w=600, h=160,
                               project="ROADSHOW DEMO",
                               drawing_no="DWG-PID-001",
                               title="Three-Phase Separator V-101 — Liquid Outlet to E-101"))

    # --- Header ---
    parts.append(f'<text x="40" y="50" {S.FONT_FAMILY} font-size="22" font-weight="700">P&amp;ID — Three-Phase Separator System (V-101)</text>')
    parts.append(f'<text x="40" y="78" {S.FONT_FAMILY} font-size="14" fill="#666">ISA-5.1 SYNTHETIC SAMPLE — for Bedrock Agentic AI demo</text>')

    svg = S.svg_doc(W, H, "\n".join(parts))

    gt = {
        "drawing_id": "01_separator_pid",
        "drawing_type": "P&ID",
        "title": "Three-Phase Separator V-101 — Liquid Outlet to E-101",
        "drawing_no": "DWG-PID-001",
        "canvas_size": {"width": W, "height": H},
        "equipment": equipment,
        "instruments": instruments,
        "lines": lines,
        "connections": connections,
        "expected_anomalies": [],  # baseline drawing has no rule violations
    }
    return svg, gt


def main() -> int:
    svg, gt = build()
    svg_path = SAMPLES / "01_separator_pid.svg"
    pdf_path = SAMPLES / "01_separator_pid.pdf"
    gt_path = GT / "01_separator_pid.json"

    svg_path.write_text(svg)
    gt_path.write_text(json.dumps(gt, indent=2))

    import cairosvg
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(pdf_path), output_width=W, output_height=H)
    print(f"WROTE: {svg_path} ({svg_path.stat().st_size} B)")
    print(f"WROTE: {pdf_path} ({pdf_path.stat().st_size} B)")
    print(f"WROTE: {gt_path}")
    print(f"GT counts: equipment={len(gt['equipment'])} instruments={len(gt['instruments'])} "
          f"lines={len(gt['lines'])} connections={len(gt['connections'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
