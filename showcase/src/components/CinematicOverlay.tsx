import { useMemo } from "react";
import type { Geometry } from "../lib/types";
import type { StoryStep } from "../lib/storyboard";

interface Props {
  geometry: Geometry;
  canvas: { width: number; height: number };
  step: StoryStep;
  stepProgress: number; // 0..1 within current beat
  /** which step ids have already completed (their elements stay lit) */
  completedStepIds: Set<string>;
}

const COLORS = {
  equipment: "var(--accent)", // cyan
  instrument: "#f59e0b", // amber
  valve: "#f97316", // orange
  line: "#64748b", // gray
  lineGlow: "var(--line-glow)",
};

const VALVE_TYPES = new Set([
  "gate_valve", "ball_valve", "control_valve", "check_valve", "safety_valve",
]);

function isValve(type: string | null | undefined): boolean {
  return !!type && VALVE_TYPES.has(type);
}

/** A reveal that ramps an element in over the first part of its beat,
 * staggered by index so they pop in sequence rather than all at once. */
function revealAt(progress: number, index: number, count: number): number {
  const per = 1 / Math.max(1, count);
  const start = index * per * 0.7; // overlap the staggers a bit
  const local = (progress - start) / (per * 1.3);
  return Math.min(1, Math.max(0, local));
}

export function CinematicOverlay({
  geometry, canvas, step, stepProgress, completedStepIds,
}: Props) {
  const w = canvas.width || 1000;
  const h = canvas.height || 1000;

  // Partition equipment into "real equipment" vs "valves" so they light
  // up in their respective beats (vision vs valve-scan).
  const { equipment, valves } = useMemo(() => {
    const eq = geometry.equipment.filter((e) => e.bbox && !isValve(e.type));
    const vv = geometry.equipment.filter((e) => e.bbox && isValve(e.type));
    return { equipment: eq, valves: vv };
  }, [geometry.equipment]);

  const instruments = useMemo(
    () => geometry.instruments.filter((i) => i.bbox),
    [geometry.instruments],
  );
  const lines = useMemo(
    () => geometry.lines.filter((l) => l.geometry && l.geometry.length > 1),
    [geometry.lines],
  );

  const id = step.id;
  const done = completedStepIds;

  // Visibility gates: an element is fully shown if its beat is complete,
  // or animating in if its beat is current.
  const showEquip = done.has("vision") || id === "vision";
  const showLines = done.has("lines") || id === "lines";
  const showFusion = done.has("fusion") || id === "fusion";
  const showValves = done.has("valves") || id === "valves";
  const showInstruments = done.has("vision") || id === "vision";

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="pointer-events-none absolute inset-0 h-full w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <filter id="sc-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* ── Process lines + traveling light ───────────────────────── */}
      {/* Every detected line lights up in the "line tracing" beat so the
          audience sees ALL drawing lines were recognized. Multi-point
          lines get a traveling-light path; single-point lines (where the
          extractor only anchored the label) get a pulsing node so they
          still register as "found". */}
      {showLines &&
        lines.map((l, i) => {
          const pts = l.geometry!;
          const rv = id === "lines" ? revealAt(stepProgress, i, lines.length) : 1;
          const isPath = pts.length > 1;

          if (!isPath) {
            const [px, py] = pts[0];
            return (
              <g key={`line-${i}`} opacity={rv}>
                <circle
                  cx={px} cy={py} r={9}
                  fill="none" stroke={COLORS.lineGlow} strokeWidth={2.5}
                  style={{ filter: "url(#sc-glow)" }}
                />
                <circle
                  cx={px} cy={py} r={4} fill={COLORS.lineGlow}
                  style={{ filter: "url(#sc-glow)", animation: "sc-glow-breathe 1.4s ease-in-out infinite" }}
                />
              </g>
            );
          }

          const d = pts.map((p, j) => `${j === 0 ? "M" : "L"} ${p[0]} ${p[1]}`).join(" ");
          const [ex, ey] = pts[pts.length - 1];
          return (
            <g key={`line-${i}`} opacity={rv}>
              {/* solid base */}
              <path d={d} fill="none" stroke={COLORS.lineGlow} strokeWidth={4} opacity={0.35} style={{ filter: "url(#sc-glow)" }} />
              {/* traveling light */}
              <path
                d={d}
                fill="none"
                stroke="#ffffff"
                strokeWidth={3}
                strokeLinecap="round"
                strokeDasharray="18 200"
                style={{ animation: "sc-dash 2.4s linear infinite", filter: "url(#sc-glow)" }}
                opacity={0.95}
              />
              {/* endpoint node — marks the traced terminal */}
              <circle cx={ex} cy={ey} r={5} fill={COLORS.lineGlow} style={{ filter: "url(#sc-glow)" }} />
            </g>
          );
        })}
      {/* Line-count badge during the tracing beat — reinforces "all lines found" */}
      {id === "lines" && lines.length > 0 && (
        <g>
          <rect
            x={w - 360} y={40} width={320} height={70} rx={12}
            fill="color-mix(in srgb, var(--bg-surface) 88%, transparent)"
            stroke={COLORS.lineGlow} strokeWidth={2}
          />
          <text x={w - 340} y={72} fill={COLORS.lineGlow} fontSize={26} fontWeight="700" fontFamily="monospace">
            {Math.round(lines.length * stepProgress)} / {lines.length}
          </text>
          <text x={w - 340} y={98} fill="#94a3b8" fontSize={18}>
            배관 라인 인식 중
          </text>
        </g>
      )}

      {/* ── Fusion connectors (tag ↔ bbox center ticks) ───────────── */}
      {showFusion &&
        equipment.slice(0, 40).map((e, i) => {
          if (!e.bbox) return null;
          const [x1, y1, x2, y2] = e.bbox;
          const cx = (x1 + x2) / 2;
          const cy = (y1 + y2) / 2;
          const rv = id === "fusion" ? revealAt(stepProgress, i, Math.min(40, equipment.length)) : 1;
          return (
            <circle
              key={`fus-${i}`}
              cx={cx} cy={cy} r={6}
              fill="var(--accent)"
              opacity={rv * 0.9}
              style={{ filter: "url(#sc-glow)" }}
            />
          );
        })}

      {/* ── Equipment bboxes (cyan) ───────────────────────────────── */}
      {showEquip &&
        equipment.map((e, i) => {
          if (!e.bbox) return null;
          const [x1, y1, x2, y2] = e.bbox;
          const rv = id === "vision" ? revealAt(stepProgress, i, equipment.length) : 1;
          return (
            <g key={`eq-${i}`} opacity={rv}>
              <rect
                x={x1} y={y1} width={x2 - x1} height={y2 - y1}
                fill="none" stroke={COLORS.equipment} strokeWidth={3}
                rx={4} style={{ filter: "url(#sc-glow)" }}
              />
            </g>
          );
        })}

      {/* ── Instruments (amber) ───────────────────────────────────── */}
      {showInstruments &&
        instruments.map((ins, i) => {
          if (!ins.bbox) return null;
          const [x1, y1, x2, y2] = ins.bbox;
          const rv = id === "vision" ? revealAt(stepProgress, i, instruments.length) : 1;
          const cx = (x1 + x2) / 2;
          const cy = (y1 + y2) / 2;
          const r = Math.max(10, (x2 - x1) / 2);
          return (
            <circle
              key={`ins-${i}`}
              cx={cx} cy={cy} r={r}
              fill="none" stroke={COLORS.instrument} strokeWidth={2.5}
              opacity={rv * 0.9}
            />
          );
        })}

      {/* ── Inline valves (orange, light up in the valve beat) ────── */}
      {showValves &&
        valves.map((v, i) => {
          if (!v.bbox) return null;
          const [x1, y1, x2, y2] = v.bbox;
          const rv = id === "valves" ? revealAt(stepProgress, i, Math.max(1, valves.length)) : 1;
          return (
            <rect
              key={`v-${i}`}
              x={x1} y={y1} width={x2 - x1} height={y2 - y1}
              fill={COLORS.valve} fillOpacity={0.25}
              stroke={COLORS.valve} strokeWidth={3}
              opacity={rv} style={{ filter: "url(#sc-glow)" }}
            />
          );
        })}
    </svg>
  );
}
