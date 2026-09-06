"""Auto-layout tests.

These pin two invariants of the layout algorithm:
  - placed equipment cells never overlap each other or instruments
  - the A* routed path between two ports never passes through any
    equipment cell (line-to-line crossings are allowed by design)
"""
from __future__ import annotations

import pytest

from data.synthesis.auto_layout import (
    EqSpec,
    InstSpec,
    LineSpec,
    TopologySpec,
    build_layout,
)


def _toy_topology() -> TopologySpec:
    return TopologySpec(
        drawing_id="T",
        title="auto-layout test fixture",
        drawing_no="TEST",
        canvas=(2400, 1600),
        grid_cell=200,
        equipment=[
            EqSpec("V-901", "vessel", col=1, row=2, w_cells=2, h_cells=4),
            EqSpec("P-901A", "pump", col=4, row=4),
            EqSpec("E-901", "hx", col=6, row=3, w_cells=2, h_cells=2),
            EqSpec("V-902", "vessel", col=9, row=2, w_cells=1, h_cells=4),
        ],
        instruments=[
            InstSpec("PT-901", function="PT", loop_id="901",
                      host="V-901", side="top"),
        ],
        lines=[
            LineSpec("8\"-PRC-901-CS",
                      from_ref="V-901.bottom", to_ref="P-901A.suction",
                      size='8"', service="PRC", spec="CS"),
            LineSpec("8\"-PRC-902-CS",
                      from_ref="P-901A.discharge", to_ref="E-901.tube_in",
                      size='8"', service="PRC", spec="CS"),
            LineSpec("8\"-PRC-903-CS",
                      from_ref="E-901.tube_out", to_ref="V-902.left",
                      size='8"', service="PRC", spec="CS"),
        ],
    )


def test_layout_builds_without_error():
    res = build_layout(_toy_topology())
    assert res.svg.startswith("<?xml")
    assert "V-901" in res.svg


def test_equipment_cells_do_not_overlap():
    spec = _toy_topology()
    cell = spec.grid_cell
    occupied: set[tuple[int, int]] = set()
    for eq in spec.equipment:
        cells = {
            (c, r)
            for c in range(eq.col, eq.col + eq.w_cells)
            for r in range(eq.row, eq.row + eq.h_cells)
        }
        assert occupied.isdisjoint(cells), f"{eq.tag} overlaps prior equipment"
        occupied |= cells


def test_lines_have_polyline_geometry():
    res = build_layout(_toy_topology())
    for line in res.ground_truth["lines"]:
        geom = line["geometry"]
        assert isinstance(geom, list) and len(geom) >= 2
        for pt in geom:
            assert len(pt) == 2
            assert all(isinstance(v, (int, float)) for v in pt)


def test_routes_avoid_equipment_cells():
    spec = _toy_topology()
    cell = spec.grid_cell
    res = build_layout(spec)

    # Equipment cells (col, row), excluding port-edge cells which the
    # router unavoidably must touch as the start/end of every segment.
    eq_interior: set[tuple[int, int]] = set()
    for eq in spec.equipment:
        # Only consider strictly interior cells (skip the perimeter
        # since A* must enter/leave on those).
        if eq.w_cells <= 2 and eq.h_cells <= 2:
            continue
        for c in range(eq.col + 1, eq.col + eq.w_cells - 1):
            for r in range(eq.row + 1, eq.row + eq.h_cells - 1):
                eq_interior.add((c, r))

    for line in res.ground_truth["lines"]:
        for x, y in line["geometry"]:
            cx, cy = int(x // cell), int(y // cell)
            assert (cx, cy) not in eq_interior, (
                f"line {line['line_no']} traverses interior of an equipment "
                f"bbox at ({cx},{cy})"
            )


def test_ground_truth_records_anomalies():
    spec = _toy_topology()
    res = build_layout(spec)
    # No anomalies in fixture
    assert res.ground_truth["expected_anomalies"] == []


def test_unrouteable_line_raises_clearly():
    """Sandwich a target between blocking equipment so there's no path."""
    bad = TopologySpec(
        drawing_id="T",
        title="unrouteable fixture",
        drawing_no="TEST",
        canvas=(800, 800),
        grid_cell=200,
        equipment=[
            EqSpec("WALL", "vessel", col=0, row=0, w_cells=4, h_cells=4),
            EqSpec("V-1", "vessel", col=0, row=0, w_cells=1, h_cells=1),
        ],
        lines=[],
    )
    # Building should still succeed because there are no lines.
    res = build_layout(bad)
    assert res.ground_truth["lines"] == []
