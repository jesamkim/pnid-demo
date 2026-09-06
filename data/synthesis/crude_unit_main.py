"""Crude unit feed section P&ID — synthetic ISA-5.1 drawing for the demo.

Layout (3200x1800 canvas):
  Row A (process, top half):
    T-101 (charge tank) → P-101A/B (with PSV-101) → E-101 → E-102 → F-101 → C-101 (column)
    C-101 top → V-101 (overhead drum) → P-102A/B → reflux back to C-101 + product out
    C-101 bottom → V-102 (bottoms drum) → product out
  Row B (utility, bottom strip):
    Steam header to F-101, CW header to E-103 (column overhead cooler).

Object count target: 8 equipment + 12 instruments + 18 lines = 38.

This module emits BOTH the SVG and the ground-truth JSON via main(), so
the same coordinate values feed both the rendered drawing and the
machine-readable bbox/geometry contract that backend search uses.
"""
from __future__ import annotations

import json
from pathlib import Path

import cairosvg

from data.synthesis import isa_svg as I

ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLES = ROOT / "data" / "samples"
GT = ROOT / "data" / "ground_truth"
SAMPLES.mkdir(parents=True, exist_ok=True)
GT.mkdir(parents=True, exist_ok=True)

W, H = 3200, 1800


def build() -> tuple[str, dict]:
    """Build the SVG body and the ground-truth dict in one pass."""

    body_parts: list[str] = []
    equipment: list[dict] = []
    instruments: list[dict] = []
    lines: list[dict] = []
    connections: list[dict] = []

    # =========================================================
    # Row A — process line (y ≈ 350..900)
    # =========================================================

    # T-101 charge tank
    t101 = I.vessel(cx=300, cy=600, w=240, h=520, tag="T-101")
    body_parts.append(t101.svg)
    equipment.append({"tag": "T-101", "type": "tank",
                       "service": "Crude Charge Tank", "bbox": list(t101.bbox)})

    # P-101A / P-101B charge pumps (parallel)
    p101a = I.pump_centrifugal(cx=620, cy=520, r=55, tag="P-101A")
    p101b = I.pump_centrifugal(cx=620, cy=720, r=55, tag="P-101B")
    body_parts.append(p101a.svg)
    body_parts.append(p101b.svg)
    equipment.append({"tag": "P-101A", "type": "pump",
                       "service": "Crude Charge Pump A", "bbox": list(p101a.bbox)})
    equipment.append({"tag": "P-101B", "type": "pump",
                       "service": "Crude Charge Pump B (spare)", "bbox": list(p101b.bbox)})

    # PSV-101 protecting V-101 overhead drum (relief to flare). The symbol
    # is placed up and slightly right of P-101A so it sits visually on the
    # process side of the unit; the connection in the model attaches it
    # to V-101 so the validator's "vessel without PSV" rule treats V-101
    # as protected.
    psv101 = I.psv(cx=760, cy=380, size=42, tag="PSV-101")
    body_parts.append(psv101.svg)
    equipment.append({"tag": "PSV-101", "type": "psv",
                       "service": "V-101 overhead drum overpressure relief",
                       "bbox": list(psv101.bbox)})

    # E-101 pre-heater (cold preheat from product)
    e101 = I.heat_exchanger(cx=940, cy=620, w=200, h=160, tag="E-101")
    body_parts.append(e101.svg)
    equipment.append({"tag": "E-101", "type": "heat_exchanger",
                       "service": "Crude/product preheat",
                       "bbox": list(e101.bbox)})

    # E-102 mid-temp HX
    e102 = I.heat_exchanger(cx=1280, cy=620, w=200, h=160, tag="E-102")
    body_parts.append(e102.svg)
    equipment.append({"tag": "E-102", "type": "heat_exchanger",
                       "service": "Crude/HVGO heat",
                       "bbox": list(e102.bbox)})

    # F-101 fired heater
    f101 = I.fired_heater(cx=1640, cy=620, w=300, h=320, tag="F-101")
    body_parts.append(f101.svg)
    equipment.append({"tag": "F-101", "type": "furnace",
                       "service": "Crude charge heater", "bbox": list(f101.bbox)})

    # C-101 distillation column
    c101 = I.column(cx=2080, cy=620, w=220, h=900, tag="C-101", n_trays=10)
    body_parts.append(c101.svg)
    equipment.append({"tag": "C-101", "type": "column",
                       "service": "Atmospheric distillation tower", "bbox": list(c101.bbox)})

    # V-101 overhead drum (top right)
    v101 = I.vessel(cx=2540, cy=320, w=200, h=300, tag="V-101")
    body_parts.append(v101.svg)
    equipment.append({"tag": "V-101", "type": "vessel",
                       "service": "Overhead reflux drum", "bbox": list(v101.bbox)})

    # P-102A/B reflux pumps
    p102a = I.pump_centrifugal(cx=2740, cy=520, r=50, tag="P-102A")
    p102b = I.pump_centrifugal(cx=2740, cy=680, r=50, tag="P-102B")
    body_parts.append(p102a.svg)
    body_parts.append(p102b.svg)
    equipment.append({"tag": "P-102A", "type": "pump",
                       "service": "Reflux pump A", "bbox": list(p102a.bbox)})
    equipment.append({"tag": "P-102B", "type": "pump",
                       "service": "Reflux pump B (spare)", "bbox": list(p102b.bbox)})

    # V-102 bottoms drum (lower right)
    v102 = I.vessel(cx=2540, cy=1280, w=200, h=260, tag="V-102")
    body_parts.append(v102.svg)
    equipment.append({"tag": "V-102", "type": "vessel",
                       "service": "Bottoms surge drum", "bbox": list(v102.bbox)})

    # =========================================================
    # Instruments (12)
    # =========================================================

    inst_specs = [
        # On T-101 (placed to the left so it doesn't overlap the vessel tag)
        ("LT", "101", 130, 920, "T-101", (200, 860)),  # tank level
        # FT on T-101 -> P-101 line (between tank and pump suction)
        ("FT", "101", 510, 380, "P-101A", (510, 520)),  # flow upstream of pumps
        ("PT", "102", 870, 380, "P-101A", (840, 520)),  # discharge pressure
        # On E-101 outlet (TT)
        ("TT", "103", 1060, 540, "E-101", (1020, 580)),  # E-101 outlet temp
        # On E-102 outlet (TT)
        ("TT", "104", 1400, 540, "E-102", (1360, 580)),  # E-102 outlet temp
        # F-101 outlet TT (high-temp)
        ("TT", "105", 1820, 480, "F-101", (1790, 540)),  # F-101 process out
        # On C-101 (PT and LT)
        ("PT", "106", 2200, 250, "C-101", (2190, 320)),  # column top pressure
        ("LT", "107", 2200, 980, "C-101", (2190, 920)),  # column sump level
        # V-101 LT
        ("LT", "108", 2660, 320, "V-101", (2640, 320)),  # OVHD drum level
        # FIC on reflux to column (placed below the discharge line)
        ("FIC", "109", 2900, 380, "P-102A", (2820, 520)),  # reflux flow
        # V-102 LT
        ("LT", "110", 2660, 1280, "V-102", (2640, 1280)),  # bottoms level
        # FIC on bottoms product (above the bottoms line so it doesn't overlap)
        ("FIC", "111", 2900, 1180, "V-102", (2820, 1280)),  # bottoms flow
    ]
    for fn, loop, ix, iy, located_on, _ in inst_specs:
        inst = I.instrument(cx=ix, cy=iy, r=36, function=fn, loop=loop)
        body_parts.append(inst.svg)
        instruments.append({"tag": f"{fn}-{loop}", "function": fn, "loop_id": loop,
                             "located_on": located_on, "bbox": list(inst.bbox)})

    # Signal lines (instrument bubble to its host) — visual only, not in lines[]
    for fn, loop, ix, iy, _, host_pt in inst_specs:
        body_parts.append(I.signal((ix, iy + 36), host_pt, elbow="v"))

    # =========================================================
    # Lines (18) — each with polyline geometry
    # =========================================================

    def ln(line_no: str, size: str, service: str, spec: str | None,
           from_tag: str | None, to_tag: str | None,
           geometry: list[tuple[float, float]]) -> None:
        # Render the polyline (orthogonal segments only)
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}"
                      for i, (x, y) in enumerate(geometry))
        body_parts.append(
            f'<path d="{d}" fill="none" stroke="{I.STROKE}" stroke-width="{I.PIPE_W}" />'
        )
        # Mid-point label
        mx = (geometry[0][0] + geometry[-1][0]) / 2
        my = (geometry[0][1] + geometry[-1][1]) / 2 - 8
        body_parts.append(I.line_label(mx, my, line_no))
        lines.append({
            "line_no": line_no, "size": size, "service": service, "spec": spec,
            "from_tag": from_tag, "to_tag": to_tag,
            "geometry": [list(p) for p in geometry],
        })

    # L1 — T-101 bottom -> P-101A suction (split into A/B header)
    ln('12"-CRD-101-CS', '12"', "CRD", "CS", "T-101", "P-101A",
       [(420, 600), (480, 600), (480, 520), (565, 520)])
    # L2 — P-101A suction branch to P-101B
    ln('12"-CRD-102-CS', '12"', "CRD", "CS", "T-101", "P-101B",
       [(480, 600), (480, 720), (565, 720)])
    # L3 — P-101A discharge horizontal to header
    ln('8"-CRD-103-CS', '8"', "CRD", "CS", "P-101A", "E-101",
       [(675, 520), (760, 520), (760, 600), (840, 600)])
    # L4 — P-101B discharge to header tie
    ln('8"-CRD-104-CS', '8"', "CRD", "CS", "P-101B", "E-101",
       [(675, 720), (760, 720), (760, 640), (840, 640)])
    # L5 — PSV-101 inlet from P-101A discharge
    ln('4"-PSV-105-CS', '4"', "PSV", "CS", "P-101A", "PSV-101",
       [(720, 520), (720, 460), (760, 460), (760, 380)])
    # L6 — PSV-101 outlet to flare header (offstream)
    ln('6"-FLR-106-A106', '6"', "FLR", "A106", "PSV-101", None,
       [(760, 312), (760, 180), (480, 180)])
    # L7 — E-101 hot-out to E-102
    ln('8"-CRD-107-CS', '8"', "CRD", "CS", "E-101", "E-102",
       [(1040, 600), (1180, 600)])
    # L8 — E-102 hot-out to F-101 inlet
    ln('8"-CRD-108-CS', '8"', "CRD", "CS", "E-102", "F-101",
       [(1380, 600), (1490, 600), (1490, 700)])
    # L9 — F-101 process-out to C-101 feed (high-temp)
    ln('10"-CRD-109-1.25Cr', '10"', "CRD", "1.25Cr", "F-101", "C-101",
       [(1790, 580), (1970, 580), (1970, 620)])
    # L10 — C-101 top vapor to V-101 (via E-103 air cooler — not modelled here, simple line)
    ln('14"-OVH-110-CS', '14"', "OVH", "CS", "C-101", "V-101",
       [(2080, 175), (2080, 80), (2540, 80), (2540, 170)])
    # L11 — V-101 bottom to P-102 suction header
    ln('6"-RFX-111-CS', '6"', "RFX", "CS", "V-101", "P-102A",
       [(2540, 470), (2540, 520), (2685, 520)])
    # L12 — P-102 suction branch to B
    ln('6"-RFX-112-CS', '6"', "RFX", "CS", "V-101", "P-102B",
       [(2540, 520), (2540, 680), (2685, 680)])
    # L13 — P-102A discharge to column (reflux)
    ln('4"-RFX-113-CS', '4"', "RFX", "CS", "P-102A", "C-101",
       [(2793, 520), (2860, 520), (2860, 380), (2190, 380)])
    # L14 — Naphtha product out from V-101 to OSBL
    ln('6"-NPH-114-CS', '6"', "NPH", "CS", "V-101", None,
       [(2540, 470), (2540, 580), (2960, 580), (2960, 460), (3120, 460)])
    # L15 — C-101 bottom to V-102 (bottoms)
    ln('10"-AGO-115-CS', '10"', "AGO", "CS", "C-101", "V-102",
       [(2080, 1075), (2080, 1280), (2440, 1280)])
    # L16 — V-102 to AGO product out
    ln('8"-AGO-116-CS', '8"', "AGO", "CS", "V-102", None,
       [(2640, 1280), (2820, 1280), (2820, 1320), (3120, 1320)])
    # L17 — Steam header to F-101 fuel/atomizing (utility)
    ln('4"-MS-117-CS', '4"', "MS", "CS", None, "F-101",
       [(140, 1620), (1490, 1620), (1490, 880)])
    # L18 — Cooling water from header to E-102 (utility return)
    ln('6"-CW-118-CS', '6"', "CW", "CS", None, "E-102",
       [(140, 1700), (1280, 1700), (1280, 700)])

    # =========================================================
    # Connections (logical) — used by ISA validator
    # =========================================================
    connections.extend([
        {"from_tag": "T-101", "to_tag": "P-101A", "type": "pipe", "via_line": '12"-CRD-101-CS'},
        {"from_tag": "T-101", "to_tag": "P-101B", "type": "pipe", "via_line": '12"-CRD-102-CS'},
        # PSV-101 sits on the V-101 protection loop (visually shown
        # above P-101A but logically connected to V-101).
        {"from_tag": "V-101", "to_tag": "PSV-101", "type": "pipe", "via_line": '4"-PSV-105-CS'},
        {"from_tag": "P-101A", "to_tag": "E-101", "type": "pipe", "via_line": '8"-CRD-103-CS'},
        {"from_tag": "P-101B", "to_tag": "E-101", "type": "pipe", "via_line": '8"-CRD-104-CS'},
        {"from_tag": "E-101", "to_tag": "E-102", "type": "pipe", "via_line": '8"-CRD-107-CS'},
        {"from_tag": "E-102", "to_tag": "F-101", "type": "pipe", "via_line": '8"-CRD-108-CS'},
        {"from_tag": "F-101", "to_tag": "C-101", "type": "pipe", "via_line": '10"-CRD-109-1.25Cr'},
        {"from_tag": "C-101", "to_tag": "V-101", "type": "pipe", "via_line": '14"-OVH-110-CS'},
        {"from_tag": "V-101", "to_tag": "P-102A", "type": "pipe", "via_line": '6"-RFX-111-CS'},
        {"from_tag": "V-101", "to_tag": "P-102B", "type": "pipe", "via_line": '6"-RFX-112-CS'},
        {"from_tag": "P-102A", "to_tag": "C-101", "type": "pipe", "via_line": '4"-RFX-113-CS'},
        {"from_tag": "C-101", "to_tag": "V-102", "type": "pipe", "via_line": '10"-AGO-115-CS'},
        {"from_tag": "PT-102", "to_tag": "P-101A", "type": "signal"},
        {"from_tag": "FT-101", "to_tag": "P-101A", "type": "signal"},
        {"from_tag": "TT-103", "to_tag": "E-101", "type": "signal"},
        {"from_tag": "TT-104", "to_tag": "E-102", "type": "signal"},
        {"from_tag": "TT-105", "to_tag": "F-101", "type": "signal"},
        {"from_tag": "PT-106", "to_tag": "C-101", "type": "signal"},
        {"from_tag": "LT-107", "to_tag": "C-101", "type": "signal"},
        {"from_tag": "LT-108", "to_tag": "V-101", "type": "signal"},
        {"from_tag": "FIC-109", "to_tag": "P-102A", "type": "signal"},
        {"from_tag": "LT-110", "to_tag": "V-102", "type": "signal"},
        {"from_tag": "FIC-111", "to_tag": "V-102", "type": "signal"},
        {"from_tag": "LT-101", "to_tag": "T-101", "type": "signal"},
    ])

    # =========================================================
    # Title block
    # =========================================================
    body_parts.append(
        I.title_block(
            x=2540, y=1620, w=620, h=160,
            project="ROADSHOW DEMO",
            drawing_no="PID-CRUDE-FEED-001",
            title="Crude Charge and Feed Section",
            rev="0",
        )
    )
    body_parts.append(
        f'<text x="60" y="60" {I.TEXT_FONT} font-weight="700">P&amp;ID — Crude Unit Feed Section (Synthetic Demo)</text>'
    )
    body_parts.append(
        f'<text x="60" y="86" {I.TEXT_FONT} fill="#666">'
        "ISA-5.1 SYNTHETIC SAMPLE — for Roadshow Agentic AI demo</text>"
    )

    body = "\n".join(body_parts)
    svg = I.svg_doc(W, H, body)
    gt = {
        "drawing_id": "01",
        "drawing_type": "P&ID",
        "title": "Crude Charge and Feed Section",
        "drawing_no": "PID-CRUDE-FEED-001",
        "canvas_size": {"width": W, "height": H},
        "equipment": equipment,
        "instruments": instruments,
        "lines": lines,
        "connections": connections,
        # Intentional anomalies for the demo's ISA-5.1 panel.
        # These exercise the R1 "vessel without PSV" rule on items that
        # in reality are often protected by relief paths not drawn in
        # this excerpt (T-101 has an atmospheric vent, V-102 sits below
        # a column with its own relief, C-101 vents through V-101's
        # PSV-101). For the demo we leave them as flagged so the
        # ISA-5.1 Anomalies card has visible content.
        "expected_anomalies": [
            {
                "rule": "vessel_without_psv_protection",
                "severity": "medium",
                "violated_by": "V-102",
                "description": "Bottoms surge drum V-102 has no PSV connection in this excerpt.",
                "suggestion": "Verify PSV-102 (not modelled here) or add a relief tag.",
            },
            {
                "rule": "vessel_without_psv_protection",
                "severity": "low",
                "violated_by": "C-101",
                "description": "Distillation column C-101 has no PSV connection in this excerpt.",
                "suggestion": "C-101 vents through V-101 / PSV-101; add explicit relief tag for clarity.",
            },
        ],
    }
    return svg, gt


def main() -> None:
    svg, gt = build()
    svg_path = SAMPLES / "01_separator_pid.svg"
    pdf_path = SAMPLES / "01_separator_pid.pdf"
    gt_path = GT / "01_separator_pid.json"
    svg_path.write_text(svg, encoding="utf-8")
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(pdf_path))
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False))
    print(f"wrote {svg_path}")
    print(f"wrote {pdf_path}")
    print(f"wrote {gt_path}")
    print(f"  equipment={len(gt['equipment'])} instruments={len(gt['instruments'])} "
          f"lines={len(gt['lines'])}")


if __name__ == "__main__":
    main()
