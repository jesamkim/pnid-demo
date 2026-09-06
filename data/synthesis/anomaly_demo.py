"""Synthesize Drawing 03: Intentional anomalies for the rule-violation demo.

Anomalies embedded:
  A1) Vessel V-301 lacks any PSV (overpressure protection missing).
  A2) Instrument PT-302 floats with no signal line to any equipment or panel.
  A3) Line "8\"-FD-301-CS" labeled in two segments with conflicting spec
      ("CS" vs "SS") — pipe-spec inconsistency.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data.synthesis import isa_svg as S

OUT_DIR = Path(__file__).resolve().parent.parent.parent
W, H = 2400, 1500


def main() -> int:
    parts: list[str] = []
    equipment: list[dict] = []
    instruments: list[dict] = []
    lines: list[dict] = []
    connections: list[dict] = []

    # V-301 vessel WITHOUT a PSV (Anomaly A1)
    v301 = S.vessel(cx=550, cy=750, w=300, h=620, tag="V-301")
    parts.append(v301.svg)
    equipment.append({"tag": "V-301", "type": "vessel",
                      "service": "Two-Phase Flash Drum",
                      "bbox": list(v301.bbox)})

    # P-301 + downstream
    gv = S.gate_valve(cx=900, cy=900, size=22, tag="GV-301")
    p301 = S.pump_centrifugal(cx=1080, cy=900, r=55, tag="P-301")
    parts.append(gv.svg)
    parts.append(p301.svg)
    equipment.append({"tag": "GV-301", "type": "gate_valve", "bbox": list(gv.bbox)})
    equipment.append({"tag": "P-301", "type": "pump",
                      "service": "Bottom product pump", "bbox": list(p301.bbox)})

    parts.append(S.pipe(v301.ports["bottom"], (550, 900)))
    parts.append(S.pipe((550, 900), gv.ports["in"]))
    parts.append(S.pipe(gv.ports["out"], p301.ports["suction"]))
    # Anomaly A3: this line is labeled "CS" near the vessel and "SS" near the pump
    # Both labels MUST appear in ground_truth.lines so a downstream extractor
    # can reproduce the contradiction; the validator must flag it.
    parts.append(S.line_label(580, 895, '8"-FD-301-CS'))
    parts.append(S.line_label(940, 895, '8"-FD-301-SS'))
    lines.append({"line_no": '8"-FD-301-CS', "size": '8"', "service": "FD", "spec": "CS",
                  "from_tag": "V-301", "to_tag": "GV-301"})
    lines.append({"line_no": '8"-FD-301-SS', "size": '8"', "service": "FD", "spec": "SS",
                  "from_tag": "GV-301", "to_tag": "P-301"})
    connections.append({"from_tag": "V-301", "to_tag": "P-301", "type": "process"})

    # Discharge to BL
    parts.append(S.pipe(p301.ports["discharge"], (2300, 900)))
    parts.append(S.line_label(1500, 895, '6"-FD-302-CS'))
    parts.append(f'<text x="2310" y="905" {S.TEXT_FONT}>TO STORAGE</text>')
    lines.append({"line_no": '6"-FD-302-CS', "size": '6"', "service": "FD", "spec": "CS",
                  "from_tag": "P-301", "to_tag": "BL"})

    # Vapor outlet (no PSV — direct to vent header is illegal — but here just to vent)
    parts.append(S.pipe(v301.ports["top"], (1900, 350), elbow="h"))
    parts.append(S.line_label(900, 340, '6"-V-303-CS'))
    parts.append(f'<text x="1910" y="355" {S.TEXT_FONT}>TO VENT HEADER (no PSV upstream)</text>')
    lines.append({"line_no": '6"-V-303-CS', "size": '6"', "service": "V", "spec": "CS",
                  "from_tag": "V-301", "to_tag": "VENT_HEADER"})

    # Inlet line
    parts.append(S.pipe((100, 600), v301.ports["left"]))
    parts.append(S.line_label(140, 590, '6"-FG-300-CS'))
    lines.append({"line_no": '6"-FG-300-CS', "size": '6"', "service": "FG", "spec": "CS",
                  "from_tag": "INLET", "to_tag": "V-301"})

    # Instruments
    pt301 = S.instrument(cx=400, cy=520, r=32, function="PT", loop="301")
    parts.append(pt301.svg)
    parts.append(S.signal((432, 520), (538, 520), elbow="h"))
    instruments.append({"tag": "PT-301", "function": "PT", "loop_id": "301",
                        "located_on": "V-301", "bbox": list(pt301.bbox)})

    lit = S.instrument(cx=400, cy=950, r=32, function="LIT", loop="301")
    parts.append(lit.svg)
    parts.append(S.signal((432, 950), (538, 950), elbow="h"))
    instruments.append({"tag": "LIT-301", "function": "LIT", "loop_id": "301",
                        "located_on": "V-301", "bbox": list(lit.bbox)})

    ft = S.instrument(cx=1300, cy=820, r=32, function="FT", loop="301")
    parts.append(ft.svg)
    parts.append(S.signal((1300, 852), (1300, 870)))
    instruments.append({"tag": "FT-301", "function": "FT", "loop_id": "301",
                        "located_on": '6"-FD-302-CS', "bbox": list(ft.bbox)})

    # Anomaly A2: PT-302 floats with no signal line
    orphan = S.instrument(cx=1850, cy=1180, r=32, function="PT", loop="302")
    parts.append(orphan.svg)
    instruments.append({"tag": "PT-302", "function": "PT", "loop_id": "302",
                        "located_on": "UNKNOWN", "bbox": list(orphan.bbox)})

    # Title block
    parts.append(S.title_block(x=W - 600 - 40, y=H - 160 - 40, w=600, h=160,
                               project="ROADSHOW DEMO",
                               drawing_no="DWG-PID-003 (rev with intentional issues)",
                               title="Flash Drum V-301 — anomaly demo set"))
    parts.append(f'<text x="40" y="50" {S.FONT_FAMILY} font-size="22" font-weight="700">P&amp;ID — Flash Drum V-301 (Anomaly Demo)</text>')
    parts.append(f'<text x="40" y="78" {S.FONT_FAMILY} font-size="14" fill="#666">ISA-5.1 SYNTHETIC SAMPLE — INTENTIONAL ISSUES — for Bedrock Agentic AI demo</text>')

    svg = S.svg_doc(W, H, "\n".join(parts))

    expected = [
        {"rule": "vessel_without_psv_protection",
         "violated_by": "V-301",
         "description": "Pressure vessel V-301 has no PSV in this drawing"},
        {"rule": "orphan_instrument",
         "violated_by": "PT-302",
         "description": "PT-302 has no signal line to any equipment or panel"},
        {"rule": "pipe_spec_inconsistency",
         "violated_by": '8"-FD-301-CS / 8"-FD-301-SS',
         "description": "Same line labeled CS near V-301 and SS near P-301"},
    ]

    gt = {"drawing_id": "03_anomaly_demo", "drawing_type": "P&ID",
          "title": "Flash Drum V-301 — anomaly demo set",
          "drawing_no": "DWG-PID-003",
          "canvas_size": {"width": W, "height": H},
          "equipment": equipment, "instruments": instruments,
          "lines": lines, "connections": connections,
          "expected_anomalies": expected}

    samples = OUT_DIR / "data" / "samples"
    gt_dir = OUT_DIR / "data" / "ground_truth"
    (samples / "03_anomaly_demo.svg").write_text(svg)
    (gt_dir / "03_anomaly_demo.json").write_text(json.dumps(gt, indent=2))

    import cairosvg
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(samples / "03_anomaly_demo.pdf"),
                     output_width=W, output_height=H)
    print(f"WROTE: 03_anomaly_demo.svg/pdf, ground_truth json")
    print(f"GT counts: equipment={len(equipment)} instruments={len(instruments)} "
          f"lines={len(lines)} connections={len(connections)}")
    print(f"Expected anomalies: {len(expected)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
