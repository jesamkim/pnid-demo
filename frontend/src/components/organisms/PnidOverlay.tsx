/**
 * PnidOverlay — phase-aware SVG layer rendered on top of the drawing.
 *
 * Visibility per phase (drives both Replay and live extract):
 *   - idle:            no overlay (raw drawing only)
 *   - extracting:      equipment + instrument bbox stagger fade-in
 *   - evaluating:      bbox stay; lines appear with traveling-light
 *   - self_correcting: same as evaluating + ghost strike on the
 *                      hallucinated tag (visual cue for the demo)
 *   - finalizing:      anomaly tags pulse a warning highlight
 *   - done:            full overlay, click-to-highlight enabled
 *
 * Coordinate system: SVG viewBox = canvas size. preserveAspectRatio
 * keeps the overlay aligned with the <img> element regardless of
 * viewport sizing.
 */
import { motion, useReducedMotion } from "framer-motion";
import { useMemo } from "react";

import {
  bboxToRect,
  buildTagIndex,
  elbowPath,
  polylinePath,
} from "@/lib/geometry";
import type { GeometryResponse, Anomaly as AnomalyType } from "@/api/types";
import type { ReplayPhase } from "@/hooks/usePipelineReplay";

interface Props {
  geometry: GeometryResponse;
  activeTag: string | null;
  onSelectTag?: (tag: string | null) => void;
  /** Driving phase from Replay or Live state machines. Drives reveal animation. */
  phase: ReplayPhase;
  /** Tags flagged as anomalies (highlighted during finalizing/done phases). */
  anomalyTags?: ReadonlySet<string>;
  /** Tag the self-correction loop initially hallucinated. */
  hallucinationTag?: string | null;
}

const REVEAL_BBOX_PHASES: ReplayPhase[] = [
  "extracting",
  "evaluating",
  "self_correcting",
  "finalizing",
  "done",
];

const REVEAL_LINE_PHASES: ReplayPhase[] = [
  "evaluating",
  "self_correcting",
  "finalizing",
  "done",
];

const REVEAL_ANOMALY_PHASES: ReplayPhase[] = ["finalizing", "done"];

export function PnidOverlay({
  geometry,
  activeTag,
  onSelectTag,
  phase,
  anomalyTags,
  hallucinationTag,
}: Props) {
  const reduceMotion = useReducedMotion() ?? false;

  const showBoxes = REVEAL_BBOX_PHASES.includes(phase);
  const showLines = REVEAL_LINE_PHASES.includes(phase);
  const showAnomaly = REVEAL_ANOMALY_PHASES.includes(phase);
  const interactive = phase === "done";

  const equipmentIndex = useMemo(
    () => buildTagIndex(geometry.equipment),
    [geometry.equipment],
  );
  const instrumentIndex = useMemo(
    () => buildTagIndex(geometry.instruments),
    [geometry.instruments],
  );

  const linePaths = useMemo(() => {
    return geometry.lines
      .map((line) => {
        // Real polyline geometry wins over the synthetic elbow fallback.
        const real = polylinePath(line.geometry as any);
        if (real) return { id: line.line_no, path: real };
        const fromBbox =
          (line.from_tag && equipmentIndex.get(line.from_tag)?.bbox) ||
          (line.from_tag && instrumentIndex.get(line.from_tag)?.bbox) ||
          undefined;
        const toBbox =
          (line.to_tag && equipmentIndex.get(line.to_tag)?.bbox) ||
          (line.to_tag && instrumentIndex.get(line.to_tag)?.bbox) ||
          undefined;
        const elbow = elbowPath(fromBbox, toBbox);
        return elbow ? { id: line.line_no, path: elbow } : null;
      })
      .filter((x): x is { id: string; path: string } => x !== null);
  }, [geometry.lines, equipmentIndex, instrumentIndex]);

  return (
    <svg
      role="img"
      aria-label={`Overlay for drawing ${geometry.drawing_id}`}
      viewBox={`0 0 ${geometry.canvas.width} ${geometry.canvas.height}`}
      preserveAspectRatio="xMidYMid meet"
      className="pointer-events-none absolute inset-0 h-full w-full"
    >
      <defs>
        {/* Cinematic glow — bigger blur radius + a subtle outer halo
            around traveling-light pulses for a more deliberate "scanline"
            feel against the dark canvas. */}
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur1" />
          <feGaussianBlur stdDeviation="9" result="blur2" />
          <feMerge>
            <feMergeNode in="blur2" />
            <feMergeNode in="blur1" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        {/* Traveling-light gradient: cyan core fading to white, used by
            the moving pulse along each pipe path. */}
        <linearGradient id="travelGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="var(--accent-glow)" stopOpacity="0" />
          <stop offset="40%" stopColor="var(--line-glow)" stopOpacity="0.85" />
          <stop offset="50%" stopColor="#ecfeff" stopOpacity="1" />
          <stop offset="60%" stopColor="var(--line-glow)" stopOpacity="0.85" />
          <stop offset="100%" stopColor="var(--accent-glow)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Pipe lines first so bbox layers above */}
      <g aria-label="lines">
        {showLines &&
          linePaths.map(({ id, path }, i) => (
            <TravelingLine
              key={id}
              d={path}
              reduceMotion={reduceMotion}
              delay={i * 0.09}
            />
          ))}
      </g>

      <g aria-label="equipment">
        {showBoxes &&
          geometry.equipment.map((eq, i) => (
            <BBoxRect
              key={eq.tag}
              tag={eq.tag}
              label={eq.tag}
              bbox={eq.bbox}
              kind="equipment"
              eqType={eq.type}
              active={activeTag === eq.tag}
              flagged={!!showAnomaly && !!anomalyTags?.has(eq.tag)}
              ghosted={hallucinationTag === eq.tag && phase === "self_correcting"}
              reduceMotion={reduceMotion}
              onSelect={interactive ? onSelectTag : undefined}
              delay={i * 0.04}
            />
          ))}
      </g>

      <g aria-label="instruments">
        {showBoxes &&
          geometry.instruments.map((inst, i) => (
            <BBoxRect
              key={inst.tag}
              tag={inst.tag}
              label={inst.tag}
              bbox={inst.bbox}
              kind="instrument"
              active={activeTag === inst.tag}
              flagged={!!showAnomaly && !!anomalyTags?.has(inst.tag)}
              ghosted={false}
              reduceMotion={reduceMotion}
              onSelect={interactive ? onSelectTag : undefined}
              delay={(geometry.equipment.length + i) * 0.04}
            />
          ))}
      </g>
    </svg>
  );
}

interface BBoxRectProps {
  tag: string;
  label: string;
  bbox: [number, number, number, number];
  kind: "equipment" | "instrument";
  eqType?: string | null;
  active: boolean;
  flagged: boolean;
  ghosted: boolean;
  reduceMotion: boolean;
  onSelect?: (tag: string | null) => void;
  delay: number;
}

const VALVE_TYPES = new Set([
  "gate_valve", "ball_valve", "control_valve", "check_valve", "safety_valve",
]);

function kindColor(kind: string, eqType?: string | null): string {
  if (kind === "instrument") return "#f59e0b";
  if (eqType && VALVE_TYPES.has(eqType)) return "#f97316";
  return "#00d4ff";
}

function BBoxRect({
  tag, label, bbox, kind, eqType, active, flagged, ghosted, reduceMotion, onSelect, delay,
}: BBoxRectProps) {
  const r = bboxToRect(bbox);
  const pad = kind === "equipment" ? 8 : 4;
  const baseColor = kindColor(kind, eqType);
  const stroke = active
    ? "var(--accent)"
    : flagged
      ? "var(--warning)"
      : baseColor;
  const opacity = active ? 1 : ghosted ? 0.35 : 0.85;
  const strokeWidth = active ? 8 : 4;

  return (
    <motion.g
      role="button"
      aria-label={`${kind} ${label}${active ? " (selected)" : ""}${ghosted ? " (corrected)" : ""}`}
      onClick={() => onSelect?.(active ? null : tag)}
      style={{ pointerEvents: onSelect ? "auto" : "none", cursor: onSelect ? "pointer" : "default" }}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay, ease: "easeOut" }}
    >
      <motion.rect
        x={r.x - pad}
        y={r.y - pad}
        width={r.width + pad * 2}
        height={r.height + pad * 2}
        rx={kind === "instrument" ? Math.max(r.width, r.height) / 2 + pad : 6}
        ry={kind === "instrument" ? Math.max(r.width, r.height) / 2 + pad : 6}
        fill="transparent"
        stroke={stroke}
        strokeWidth={strokeWidth}
        opacity={opacity}
        strokeDasharray={ghosted ? "12 8" : undefined}
        animate={
          flagged && !reduceMotion
            ? { opacity: [0.85, 0.45, 0.85], strokeWidth: [strokeWidth, strokeWidth + 2, strokeWidth] }
            : active && !reduceMotion
              ? { opacity: [0.9, 0.4, 0.9], strokeWidth: [strokeWidth, strokeWidth + 2, strokeWidth] }
              : undefined
        }
        transition={
          (flagged || active) && !reduceMotion
            ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" }
            : undefined
        }
        filter={active || flagged ? "url(#glow)" : undefined}
      />
      <text
        x={r.x + r.width / 2}
        y={r.y - pad - 6}
        textAnchor="middle"
        className="pointer-events-none select-none font-mono"
        style={{
          fill: ghosted ? "var(--fg-muted)" : (active ? "var(--accent)" : flagged ? "var(--warning)" : baseColor),
          fontSize: 38,
          fontWeight: 700,
          paintOrder: "stroke",
          stroke: "var(--bg-canvas)",
          strokeWidth: 6,
          strokeOpacity: 0.85,
          textDecoration: ghosted ? "line-through" : undefined,
        }}
      >
        {label}
      </text>
    </motion.g>
  );
}

function TravelingLine({
  d, reduceMotion, delay,
}: {
  d: string;
  reduceMotion: boolean;
  delay: number;
}) {
  if (reduceMotion) {
    return (
      <path
        d={d}
        fill="none"
        stroke="var(--line-glow)"
        strokeOpacity={0.5}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    );
  }
  // Use SVG pathLength=100 to normalise every line to unit length so the
  // travelling pulse's "8% bright + 92% dim" dash pattern looks identical
  // regardless of whether the path is 200 px or 4000 px long. Without
  // this normalisation, long live-extracted polylines saw only one short
  // pulse buried in a huge gap (the "선 애니메이션이 잘못된" symptom).
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="var(--line-stroke)"
        strokeOpacity={0.35}
        strokeWidth={4}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={100}
      />
      <motion.path
        d={d}
        fill="none"
        stroke="var(--line-glow)"
        strokeOpacity={0.95}
        strokeWidth={6}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={100}
        strokeDasharray="8 92"
        initial={{ strokeDashoffset: 100 }}
        animate={{ strokeDashoffset: 0 }}
        transition={{
          duration: 3.0,
          repeat: Infinity,
          ease: "linear",
          delay,
        }}
        filter="url(#glow)"
      />
    </g>
  );
}

// Helper to derive the set of anomaly tags (used by App.tsx).
export function buildAnomalyTags(
  anomalies: ReadonlyArray<Pick<AnomalyType, "violated_by">>,
): Set<string> {
  return new Set(anomalies.map((a) => a.violated_by));
}
