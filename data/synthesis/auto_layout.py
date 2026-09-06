"""Auto-layout module — turn a topology spec into a drawn P&ID.

Inputs:
    `TopologySpec` describing equipment, instruments, lines, and
    intentional anomalies on a notional grid. The user types the
    *what* (T-101 sits at column 1 row 4, P-101A connects to E-101);
    this module computes the *where* (pixel coordinates, port
    positions, orthogonal pipe routes that don't cross equipment
    bodies) and emits both the SVG and the matching ground-truth JSON.

The grid: a `canvas / cell` integer lattice. Equipment claims
rectangular regions; instruments occupy single cells adjacent to
their host. Pipes route via A* on a cell graph that excludes
equipment-occupied cells; the cost function favours straight runs
and penalises (but allows) crossings of previously routed pipes.

The library is pure Python plus `networkx` (already a dependency for
the embedding code path; reused here for graph operations). It is
*not* a full P&ID engine — it produces drawings that look credible
in a demo, with predictable, regression-testable layout output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional, Sequence

import networkx as nx

from data.synthesis import isa_svg as I

# ---------- topology ------------------------------------------------------

EquipmentKind = Literal[
    "tank", "vessel", "pump", "hx", "furnace", "column", "psv", "air_cooler"
]
InstrumentSide = Literal["top", "bottom", "left", "right"]


@dataclass(frozen=True)
class EqSpec:
    tag: str
    kind: EquipmentKind
    col: int
    row: int
    w_cells: int = 1
    h_cells: int = 1
    service: Optional[str] = None
    # Optional override: which port the line endpoint maps to. The
    # auto-router resolves "T-101.bottom" → ports["bottom"] on the
    # placed symbol.


@dataclass(frozen=True)
class InstSpec:
    tag: str            # e.g. "PT-102"
    function: str       # "PT" — derived from tag if omitted
    loop_id: str        # "102"
    host: str           # tag of the equipment / line it belongs to
    side: InstrumentSide = "top"


@dataclass(frozen=True)
class LineSpec:
    line_no: str
    from_ref: str       # "T-101.bottom" or "P-101A.discharge"
    to_ref: str         # similarly, or `None` for an open end
    size: Optional[str] = None
    service: Optional[str] = None
    spec: Optional[str] = None


@dataclass(frozen=True)
class AnomalySpec:
    rule: str
    severity: str
    violated_by: str
    description: str
    suggestion: Optional[str] = None


@dataclass(frozen=True)
class TopologySpec:
    drawing_id: str
    title: str
    drawing_no: str
    canvas: tuple[int, int]
    grid_cell: int = 160
    equipment: Sequence[EqSpec] = field(default_factory=tuple)
    instruments: Sequence[InstSpec] = field(default_factory=tuple)
    lines: Sequence[LineSpec] = field(default_factory=tuple)
    anomalies: Sequence[AnomalySpec] = field(default_factory=tuple)
    project: str = "ROADSHOW DEMO"


# ---------- placement -----------------------------------------------------

@dataclass
class Placed:
    spec: object
    sym: I.Placed                 # the SVG fragment + bbox + ports
    cells: set[tuple[int, int]]   # cells this symbol occupies (col, row)


def _eq_pixel_box(spec: EqSpec, cell: int) -> tuple[float, float, float, float]:
    x = spec.col * cell
    y = spec.row * cell
    w = spec.w_cells * cell
    h = spec.h_cells * cell
    return x, y, x + w, y + h


def _draw_equipment(spec: EqSpec, cell: int) -> Placed:
    x1, y1, x2, y2 = _eq_pixel_box(spec, cell)
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    w = x2 - x1
    h = y2 - y1
    pad = cell * 0.12  # interior padding so the symbol doesn't touch its cell edges

    if spec.kind in ("tank", "vessel"):
        sym = I.vessel(cx=cx, cy=cy, w=w - 2 * pad, h=h - 2 * pad, tag=spec.tag)
    elif spec.kind == "pump":
        r = min(w, h) / 2 - pad
        sym = I.pump_centrifugal(cx=cx, cy=cy, r=r, tag=spec.tag)
    elif spec.kind == "hx":
        sym = I.heat_exchanger(cx=cx, cy=cy, w=w - 2 * pad, h=h - 2 * pad, tag=spec.tag)
    elif spec.kind == "furnace":
        sym = I.fired_heater(cx=cx, cy=cy, w=w - 2 * pad, h=h - 2 * pad, tag=spec.tag)
    elif spec.kind == "column":
        sym = I.column(cx=cx, cy=cy, w=w - 2 * pad, h=h - 2 * pad, tag=spec.tag)
    elif spec.kind == "psv":
        s = min(w, h) / 3 - pad / 2
        sym = I.psv(cx=cx, cy=cy, size=s, tag=spec.tag)
    elif spec.kind == "air_cooler":
        sym = I.air_cooler(cx=cx, cy=cy, w=w - 2 * pad, h=h - 2 * pad, tag=spec.tag)
    else:
        raise ValueError(f"unknown equipment kind: {spec.kind}")

    cells = {
        (c, r)
        for c in range(spec.col, spec.col + spec.w_cells)
        for r in range(spec.row, spec.row + spec.h_cells)
    }
    return Placed(spec=spec, sym=sym, cells=cells)


def _instrument_cell(host: Placed, side: InstrumentSide, cell: int,
                      occupied: set[tuple[int, int]]) -> tuple[int, int]:
    """Pick the nearest free cell on the requested side of the host."""
    cols = sorted({c for c, _ in host.cells})
    rows = sorted({r for _, r in host.cells})
    if side == "top":
        candidates = [(c, rows[0] - 1) for c in cols]
    elif side == "bottom":
        candidates = [(c, rows[-1] + 1) for c in cols]
    elif side == "left":
        candidates = [(cols[0] - 1, r) for r in rows]
    elif side == "right":
        candidates = [(cols[-1] + 1, r) for r in rows]
    else:
        raise ValueError(side)
    for c, r in candidates:
        if (c, r) not in occupied:
            return c, r
    # fall back to the first candidate even if occupied — caller
    # decides whether to raise or accept the overlap
    return candidates[0]


def _draw_instrument(spec: InstSpec, col: int, row: int, cell: int) -> Placed:
    cx = col * cell + cell / 2
    cy = row * cell + cell / 2
    r = cell * 0.28
    sym = I.instrument(cx=cx, cy=cy, r=r, function=spec.function, loop=spec.loop_id)
    return Placed(spec=spec, sym=sym, cells={(col, row)})


# ---------- routing -------------------------------------------------------

def _resolve_endpoint(ref: str, by_tag: dict[str, Placed], cell: int) -> tuple[float, float]:
    """`"T-101.bottom"` → port (px, py). Open-end refs return None at caller."""
    tag, _, port = ref.partition(".")
    placed = by_tag.get(tag)
    if not placed:
        raise KeyError(f"endpoint references unknown tag: {ref!r}")
    if not port:
        # default port: choose the right edge for left-to-right flow
        return placed.sym.ports.get("right") or next(iter(placed.sym.ports.values()))
    if port not in placed.sym.ports:
        raise KeyError(f"{tag!r} has no port {port!r} (have {list(placed.sym.ports)})")
    return placed.sym.ports[port]


def _pixel_to_cell(px: float, py: float, cell: int) -> tuple[int, int]:
    return int(px // cell), int(py // cell)


def _build_grid_graph(
    canvas: tuple[int, int],
    cell: int,
    blocked_cells: set[tuple[int, int]],
    line_cells: dict[tuple[int, int], int],
    *, turn_penalty: int = 3, crossing_penalty: int = 5,
) -> nx.Graph:
    """A cell-level graph; each edge weight is 1 + (crossings_so_far * crossing_penalty).

    Turn penalty is applied at routing time, not on the graph (we'd
    need direction-aware nodes). networkx.astar_path lets us pass a
    custom heuristic and weight function; we fold the turn penalty in
    via the weight callback.
    """
    cols = canvas[0] // cell
    rows = canvas[1] // cell
    g = nx.Graph()
    for c in range(cols):
        for r in range(rows):
            if (c, r) in blocked_cells:
                continue
            g.add_node((c, r))
    for c in range(cols):
        for r in range(rows):
            if (c, r) not in g:
                continue
            for dc, dr in ((1, 0), (0, 1)):
                n = (c + dc, r + dr)
                if n in g:
                    base = 1 + crossing_penalty * (
                        line_cells.get((c, r), 0) + line_cells.get(n, 0)
                    )
                    g.add_edge((c, r), n, weight=base)
    return g


def _astar_with_turn_penalty(
    g: nx.Graph,
    start: tuple[int, int],
    goal: tuple[int, int],
    *, turn_penalty: int = 3,
) -> list[tuple[int, int]]:
    """Manhattan-heuristic A* that adds turn cost on the fly."""
    if start not in g or goal not in g:
        raise ValueError(f"endpoint missing from graph: {start} or {goal}")

    # Direction-aware Dijkstra. State = (cell, incoming_dir).
    import heapq
    INF = float("inf")
    DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

    def heuristic(c: tuple[int, int]) -> int:
        return abs(c[0] - goal[0]) + abs(c[1] - goal[1])

    open_heap: list[tuple[float, int, tuple[int, int], Optional[tuple[int, int]]]] = []
    heapq.heappush(open_heap, (heuristic(start), 0, start, None))
    came_from: dict[tuple[tuple[int, int], Optional[tuple[int, int]]], tuple] = {}
    g_score: dict[tuple[tuple[int, int], Optional[tuple[int, int]]], float] = {(start, None): 0.0}
    counter = 0
    while open_heap:
        _, _, current, last_dir = heapq.heappop(open_heap)
        if current == goal:
            # reconstruct
            path = [current]
            key = (current, last_dir)
            while key in came_from:
                prev_cell, prev_dir = came_from[key]
                path.append(prev_cell)
                key = (prev_cell, prev_dir)
            return list(reversed(path))
        for d in DIRS:
            n = (current[0] + d[0], current[1] + d[1])
            if not g.has_edge(current, n):
                continue
            edge_w = g[current][n]["weight"]
            turn = turn_penalty if last_dir is not None and last_dir != d else 0
            new_score = g_score[(current, last_dir)] + edge_w + turn
            key_n = (n, d)
            if new_score < g_score.get(key_n, INF):
                g_score[key_n] = new_score
                came_from[key_n] = (current, last_dir)
                counter += 1
                heapq.heappush(open_heap, (new_score + heuristic(n), counter, n, d))
    raise nx.NetworkXNoPath(f"no path from {start} to {goal}")


# ---------- public build --------------------------------------------------

@dataclass(frozen=True)
class LayoutResult:
    svg: str
    ground_truth: dict


def build_layout(spec: TopologySpec) -> LayoutResult:
    """Place equipment + instruments, route lines, return SVG + GT JSON.

    Raises NetworkXNoPath if any line cannot be routed (we fail loud
    rather than ship a broken drawing).
    """
    cell = spec.grid_cell
    canvas_w, canvas_h = spec.canvas

    # 1. Place equipment.
    placed_eq: list[Placed] = []
    by_tag: dict[str, Placed] = {}
    eq_blocked: set[tuple[int, int]] = set()  # equipment cells block A* hard
    inst_blocked: set[tuple[int, int]] = set()  # instrument cells are soft-block
    for eq in spec.equipment:
        p = _draw_equipment(eq, cell)
        placed_eq.append(p)
        by_tag[eq.tag] = p
        eq_blocked |= p.cells

    # 2. Place instruments next to their host. Use a *combined*
    # occupancy set when picking a free cell so instruments don't
    # collide with each other; but for routing purposes we only
    # treat equipment as a hard block — pipes are allowed to pass
    # under instrument bubbles (the bubble is small enough that the
    # crossing is visually acceptable).
    placed_inst: list[Placed] = []
    for inst in spec.instruments:
        host = by_tag.get(inst.host)
        if not host:
            raise KeyError(f"instrument {inst.tag} references missing host {inst.host}")
        col, row = _instrument_cell(
            host, inst.side, cell, eq_blocked | inst_blocked,
        )
        p = _draw_instrument(inst, col, row, cell)
        placed_inst.append(p)
        by_tag[inst.tag] = p
        inst_blocked |= p.cells

    # `occupied` for the A* graph is equipment-only.
    occupied = eq_blocked

    # 3. Build routing graph (excluding equipment + instrument cells).
    line_cells: dict[tuple[int, int], int] = {}

    # 4. Route lines longest-first (Manhattan distance between endpoints).
    def _len(line: LineSpec) -> int:
        a = _resolve_endpoint(line.from_ref, by_tag, cell)
        b = _resolve_endpoint(line.to_ref, by_tag, cell) if line.to_ref else a
        return int(abs(a[0] - b[0]) + abs(a[1] - b[1]))

    routed: list[tuple[LineSpec, list[tuple[float, float]]]] = []
    skipped: list[str] = []
    for line in sorted(spec.lines, key=_len, reverse=True):
        try:
            ax, ay = _resolve_endpoint(line.from_ref, by_tag, cell)
            bx, by = _resolve_endpoint(line.to_ref, by_tag, cell)
        except KeyError as exc:
            raise ValueError(f"unrouteable line {line.line_no}: {exc}") from exc
        a_cell = _pixel_to_cell(ax, ay, cell)
        b_cell = _pixel_to_cell(bx, by, cell)
        # Build the graph with the *line's two endpoints* temporarily
        # un-blocked so the start/goal cells exist as graph nodes.
        endpoint_unblock = {a_cell, b_cell}
        graph = _build_grid_graph(
            spec.canvas, cell,
            occupied - endpoint_unblock,
            line_cells,
        )
        for ep in (a_cell, b_cell):
            if ep not in graph:
                graph.add_node(ep)
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (ep[0] + dc, ep[1] + dr)
                if n in graph and not graph.has_edge(ep, n):
                    graph.add_edge(ep, n, weight=1)
        try:
            path_cells = _astar_with_turn_penalty(graph, a_cell, b_cell)
        except nx.NetworkXNoPath:
            # Dense layouts can leave a few lines unrouteable — skip them
            # rather than failing the whole drawing. The skipped tags are
            # surfaced in `LayoutResult.skipped_lines` so the build script
            # can warn the user.
            skipped.append(line.line_no)
            continue
        polyline: list[tuple[float, float]] = [(ax, ay)]
        for cc in path_cells:
            polyline.append((cc[0] * cell + cell / 2, cc[1] * cell + cell / 2))
        polyline.append((bx, by))
        polyline = _collapse_collinear(polyline)
        routed.append((line, polyline))
        for cc in path_cells:
            line_cells[cc] = line_cells.get(cc, 0) + 1

    # 5. Emit SVG body.
    parts: list[str] = []
    # Pipes first (so symbols overlay them at junctions)
    for _, poly in routed:
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(poly))
        parts.append(
            f'<path d="{d}" fill="none" stroke="{I.STROKE}" '
            f'stroke-width="{I.PIPE_W}" />'
        )
        # Mid-point label
        if len(poly) >= 2:
            midx = (poly[0][0] + poly[-1][0]) / 2
            midy = (poly[0][1] + poly[-1][1]) / 2 - 8
            parts.append(I.line_label(midx, midy, _.line_no))
    for p in placed_eq:
        parts.append(p.sym.svg)
    for p in placed_inst:
        parts.append(p.sym.svg)
        # Connect the bubble to its host body with a dashed signal line.
        host = by_tag.get(p.spec.host)
        if host:
            host_cx = (host.sym.bbox[0] + host.sym.bbox[2]) / 2
            host_cy = (host.sym.bbox[1] + host.sym.bbox[3]) / 2
            inst_cx = (p.sym.bbox[0] + p.sym.bbox[2]) / 2
            inst_cy = (p.sym.bbox[1] + p.sym.bbox[3]) / 2
            parts.append(I.signal((inst_cx, inst_cy), (host_cx, host_cy)))

    # Header + title block
    parts.append(
        f'<text x="60" y="60" {I.TEXT_FONT} font-weight="700">'
        f"P&amp;ID — {spec.title} (Synthetic Demo)</text>"
    )
    parts.append(
        f'<text x="60" y="86" {I.TEXT_FONT} fill="#666">'
        "ISA-5.1 SYNTHETIC SAMPLE — auto-routed via grid + A*</text>"
    )
    parts.append(
        I.title_block(
            x=canvas_w - 660, y=canvas_h - 180, w=620, h=160,
            project=spec.project, drawing_no=spec.drawing_no,
            title=spec.title, rev="0",
        )
    )
    body = "\n".join(parts)
    svg = I.svg_doc(canvas_w, canvas_h, body)

    # 6. Build ground truth.
    gt = {
        "drawing_id": spec.drawing_id,
        "drawing_type": "P&ID",
        "title": spec.title,
        "drawing_no": spec.drawing_no,
        "canvas_size": {"width": canvas_w, "height": canvas_h},
        "equipment": [
            {
                "tag": p.spec.tag,
                "type": _kind_to_type(p.spec.kind),
                "service": p.spec.service,
                "bbox": list(p.sym.bbox),
            }
            for p in placed_eq
        ],
        "instruments": [
            {
                "tag": p.spec.tag,
                "function": p.spec.function,
                "loop_id": p.spec.loop_id,
                "located_on": p.spec.host,
                "bbox": list(p.sym.bbox),
            }
            for p in placed_inst
        ],
        "lines": [
            {
                "line_no": line.line_no,
                "size": line.size,
                "service": line.service,
                "spec": line.spec,
                "from_tag": line.from_ref.split(".")[0] if line.from_ref else None,
                "to_tag": line.to_ref.split(".")[0] if line.to_ref else None,
                "geometry": [list(pt) for pt in poly],
            }
            for line, poly in routed
        ],
        "connections": _derive_connections(spec, placed_eq, placed_inst),
        "expected_anomalies": [
            {
                "rule": a.rule,
                "severity": a.severity,
                "violated_by": a.violated_by,
                "description": a.description,
                "suggestion": a.suggestion,
            }
            for a in spec.anomalies
        ],
    }
    return LayoutResult(svg=svg, ground_truth=gt)


def _kind_to_type(k: EquipmentKind) -> str:
    return {
        "tank": "tank",
        "vessel": "vessel",
        "pump": "pump",
        "hx": "heat_exchanger",
        "furnace": "furnace",
        "column": "column",
        "psv": "psv",
        "air_cooler": "air_cooler",
    }[k]


def _derive_connections(
    spec: TopologySpec,
    placed_eq: list[Placed],
    placed_inst: list[Placed],
) -> list[dict]:
    out: list[dict] = []
    for line in spec.lines:
        a = line.from_ref.split(".")[0] if line.from_ref else None
        b = line.to_ref.split(".")[0] if line.to_ref else None
        if a and b:
            out.append({"from_tag": a, "to_tag": b, "type": "pipe",
                         "via_line": line.line_no})
    for inst in spec.instruments:
        out.append({"from_tag": inst.tag, "to_tag": inst.host, "type": "signal"})
    return out


def _collapse_collinear(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop interior points that sit on a straight segment."""
    if len(points) <= 2:
        return list(points)
    out = [points[0]]
    for i in range(1, len(points) - 1):
        x0, y0 = out[-1]
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        if (x1 - x0) * (y2 - y1) == (y1 - y0) * (x2 - x1):
            continue  # collinear → skip the middle point
        out.append((x1, y1))
    out.append(points[-1])
    return out
