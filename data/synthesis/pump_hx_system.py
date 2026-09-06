"""Synthesize Drawing 02: Pump + Heat Exchanger system.

Layout: Tank T-201 -> P-201 A/B -> E-201 -> downstream battery limit.
Adds a re-circulation line and additional instrumentation.

Equipment:   T-201 (storage tank), P-201A/B, E-201
Instruments: LIT-201, FT-201, FIC-201, TT-201, PT-201, PSV-201
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data.synthesis import isa_svg as S

OUT_DIR = Path(__file__).resolve().parent.parent.parent
W, H = 2700, 1600


def main() -> int:
    parts: list[str] = []
    equipment: list[dict] = []
    instruments: list[dict] = []
    lines: list[dict] = []
    connections: list[dict] = []

    # Tank T-201 (vertical vessel, large)
    t201 = S.vessel(cx=400, cy=720, w=300, h=620, tag="T-201")
    parts.append(t201.svg)
    equipment.append({"tag": "T-201", "type": "vessel", "service": "Feed Storage Tank",
                      "bbox": list(t201.bbox)})

    # PSV-201 on top of T-201
    psv = S.psv(cx=400, cy=320, size=40, tag="PSV-201")
    parts.append(psv.svg)
    equipment.append({"tag": "PSV-201", "type": "psv",
                      "service": "T-201 overpressure protection",
                      "set_pressure_barg": 8, "protects": "T-201",
                      "bbox": list(psv.bbox)})
    parts.append(S.pipe(t201.ports["top"], psv.ports["in"]))
    parts.append(S.pipe(psv.ports["out"], (180, 220), elbow="v"))
    parts.append(f'<text x="80" y="220" {S.TEXT_FONT}>TO FLARE</text>')
    parts.append(S.line_label(220, 240, '3"-PSV-201'))
    connections.append({"from_tag": "T-201", "to_tag": "PSV-201", "type": "process"})
    connections.append({"from_tag": "PSV-201", "to_tag": "FLARE", "type": "process"})
    lines.append({"line_no": '3"-PSV-201', "size": '3"', "service": "PSV",
                  "from_tag": "PSV-201", "to_tag": "FLARE"})

    # P-201A/B
    p201a = S.pump_centrifugal(cx=1100, cy=850, r=55, tag="P-201A")
    p201b = S.pump_centrifugal(cx=1100, cy=1080, r=55, tag="P-201B")
    parts.append(p201a.svg)
    parts.append(p201b.svg)
    equipment.append({"tag": "P-201A", "type": "pump",
                      "service": "Feed Pump (Main)", "bbox": list(p201a.bbox)})
    equipment.append({"tag": "P-201B", "type": "pump",
                      "service": "Feed Pump (Spare)", "bbox": list(p201b.bbox)})

    # Suction valves
    gva = S.gate_valve(cx=920, cy=850, size=22, tag="GV-201A")
    gvb = S.gate_valve(cx=920, cy=1080, size=22, tag="GV-201B")
    parts.append(gva.svg)
    parts.append(gvb.svg)
    equipment.append({"tag": "GV-201A", "type": "gate_valve", "bbox": list(gva.bbox)})
    equipment.append({"tag": "GV-201B", "type": "gate_valve", "bbox": list(gvb.bbox)})

    # Tank outlet -> tee -> two pumps
    parts.append(S.pipe(t201.ports["bottom"], (400, 850)))
    parts.append(S.pipe((400, 850), gva.ports["in"]))
    parts.append(S.pipe((400, 850), (400, 1080)))
    parts.append(S.pipe((400, 1080), gvb.ports["in"]))
    parts.append(S.pipe(gva.ports["out"], p201a.ports["suction"]))
    parts.append(S.pipe(gvb.ports["out"], p201b.ports["suction"]))
    parts.append(S.line_label(420, 845, '6"-FD-201-CS'))
    lines.append({"line_no": '6"-FD-201-CS', "size": '6"', "service": "FD", "spec": "CS",
                  "from_tag": "T-201", "to_tag": "P-201A/B"})
    connections.append({"from_tag": "T-201", "to_tag": "P-201A", "type": "process"})
    connections.append({"from_tag": "T-201", "to_tag": "P-201B", "type": "process"})

    # Discharge -> common header -> E-201
    gvd = S.gate_valve(cx=1300, cy=850, size=22, tag="GV-202")
    parts.append(gvd.svg)
    equipment.append({"tag": "GV-202", "type": "gate_valve", "bbox": list(gvd.bbox)})
    parts.append(S.pipe(p201a.ports["discharge"], gvd.ports["in"]))
    parts.append(S.pipe(p201b.ports["discharge"], (1300, 1080), elbow="h"))
    parts.append(S.pipe((1300, 1080), (1300, 850), elbow="v"))

    # Heat exchanger E-201
    e201 = S.heat_exchanger(cx=1800, cy=850, w=260, h=170, tag="E-201")
    parts.append(e201.svg)
    equipment.append({"tag": "E-201", "type": "heat_exchanger",
                      "service": "Feed Preheater", "bbox": list(e201.bbox)})
    parts.append(S.pipe(gvd.ports["out"], e201.ports["tube_in"]))
    parts.append(S.line_label(1500, 845, '4"-FD-202-CS'))
    lines.append({"line_no": '4"-FD-202-CS', "size": '4"', "service": "FD", "spec": "CS",
                  "from_tag": "P-201A/B", "to_tag": "E-201"})
    connections.append({"from_tag": "P-201A", "to_tag": "E-201", "type": "process"})
    connections.append({"from_tag": "P-201B", "to_tag": "E-201", "type": "process"})

    # E-201 outlet to BL
    parts.append(S.pipe(e201.ports["tube_out"], (2400, e201.ports["tube_out"][1])))
    parts.append(S.line_label(2200, e201.ports["tube_out"][1] - 8, '4"-FD-203-CS'))
    parts.append(f'<text x="2410" y="{e201.ports["tube_out"][1]+5}" {S.TEXT_FONT}>TO REACTOR (B.L.)</text>')
    lines.append({"line_no": '4"-FD-203-CS', "size": '4"', "service": "FD", "spec": "CS",
                  "from_tag": "E-201", "to_tag": "BL"})

    # Steam shell-side (HP steam in, condensate out)
    steam_in_x = e201.ports["shell_in"][0]
    steam_in_y = e201.ports["shell_in"][1]
    steam_out_x = e201.ports["shell_out"][0]
    steam_out_y = e201.ports["shell_out"][1]
    parts.append(S.pipe((steam_in_x, 1280), (steam_in_x, steam_in_y), elbow="v"))
    parts.append(S.pipe((steam_out_x, steam_out_y), (steam_out_x, 1280), elbow="v"))
    parts.append(S.line_label(steam_in_x + 8, 1260, '4"-ST-204-CS'))
    parts.append(S.line_label(steam_out_x + 8, 1260, '3"-CD-205-CS'))
    parts.append(f'<text x="{steam_in_x - 30}" y="1300" {S.TEXT_FONT}>HP STEAM</text>')
    parts.append(f'<text x="{steam_out_x - 40}" y="1300" {S.TEXT_FONT}>CONDENSATE</text>')
    lines.append({"line_no": '4"-ST-204-CS', "size": '4"', "service": "ST", "spec": "CS",
                  "from_tag": "STEAM_HEADER", "to_tag": "E-201"})
    lines.append({"line_no": '3"-CD-205-CS', "size": '3"', "service": "CD", "spec": "CS",
                  "from_tag": "E-201", "to_tag": "CD_HEADER"})

    # Instruments
    lit = S.instrument(cx=240, cy=900, r=32, function="LIT", loop="201")
    parts.append(lit.svg)
    parts.append(S.signal((272, 900), (385, 900), elbow="h"))
    instruments.append({"tag": "LIT-201", "function": "LIT", "loop_id": "201",
                        "located_on": "T-201", "bbox": list(lit.bbox)})

    pt = S.instrument(cx=240, cy=520, r=32, function="PT", loop="201")
    parts.append(pt.svg)
    parts.append(S.signal((272, 520), (385, 520), elbow="h"))
    instruments.append({"tag": "PT-201", "function": "PT", "loop_id": "201",
                        "located_on": "T-201", "bbox": list(pt.bbox)})

    ft = S.instrument(cx=1500, cy=730, r=32, function="FT", loop="201")
    parts.append(ft.svg)
    parts.append(S.signal((1500, 762), (1500, 820)))
    instruments.append({"tag": "FT-201", "function": "FT", "loop_id": "201",
                        "located_on": '4"-FD-202-CS', "bbox": list(ft.bbox)})

    fic = S.instrument(cx=1500, cy=600, r=32, function="FIC", loop="201")
    parts.append(fic.svg)
    parts.append(S.signal((1500, 632), (1500, 698)))
    instruments.append({"tag": "FIC-201", "function": "FIC", "loop_id": "201",
                        "located_on": "panel", "bbox": list(fic.bbox)})
    connections.append({"from_tag": "FT-201", "to_tag": "FIC-201", "type": "signal"})

    tt = S.instrument(cx=2150, cy=720, r=32, function="TT", loop="201")
    parts.append(tt.svg)
    parts.append(S.signal((2150, 752), (2150, 820)))
    instruments.append({"tag": "TT-201", "function": "TT", "loop_id": "201",
                        "located_on": "E-201 outlet", "bbox": list(tt.bbox)})

    # Title block + header
    parts.append(S.title_block(x=W - 600 - 40, y=H - 160 - 40, w=600, h=160,
                               project="ROADSHOW DEMO", drawing_no="DWG-PID-002",
                               title="Feed Pump Set + Preheater (T-201 / P-201 / E-201)"))
    parts.append(f'<text x="40" y="50" {S.FONT_FAMILY} font-size="22" font-weight="700">P&amp;ID — Feed Pump and Preheater System</text>')
    parts.append(f'<text x="40" y="78" {S.FONT_FAMILY} font-size="14" fill="#666">ISA-5.1 SYNTHETIC SAMPLE — for Bedrock Agentic AI demo</text>')

    svg = S.svg_doc(W, H, "\n".join(parts))

    gt = {"drawing_id": "02_pump_hx_system", "drawing_type": "P&ID",
          "title": "Feed Pump Set + Preheater System",
          "drawing_no": "DWG-PID-002",
          "canvas_size": {"width": W, "height": H},
          "equipment": equipment, "instruments": instruments,
          "lines": lines, "connections": connections,
          "expected_anomalies": []}

    samples = OUT_DIR / "data" / "samples"
    gt_dir = OUT_DIR / "data" / "ground_truth"
    (samples / "02_pump_hx_system.svg").write_text(svg)
    (gt_dir / "02_pump_hx_system.json").write_text(json.dumps(gt, indent=2))

    import cairosvg
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(samples / "02_pump_hx_system.pdf"),
                     output_width=W, output_height=H)
    print(f"WROTE: 02_pump_hx_system.svg/pdf, ground_truth json")
    print(f"GT counts: equipment={len(equipment)} instruments={len(instruments)} "
          f"lines={len(lines)} connections={len(connections)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
