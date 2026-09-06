/**
 * Storyboard — the cinematic script for the replay.
 *
 * The live pipeline emits ~150 fine-grained ProgressEvents (one per
 * fusion match, per zone, per correction iter, ...). That's far too
 * granular for a 30-second hook. We collapse them into a fixed set of
 * AUDIENCE-FACING steps, each with its own Korean copy, accent color,
 * duration, and the visual effect the canvas should run during it.
 *
 * The mapping from raw `stage` → storyboard step is by prefix, so it's
 * robust to the exact event counts in the frozen data.
 */
import type { FrozenEvent } from "./types";

export type EffectKind =
  | "scan-sweep" // a light bar sweeps the drawing (render)
  | "ocr-flash" // text blocks flash on
  | "badge-flip" // ISA/DIN convention badge flips in
  | "reveal-equipment" // equipment bboxes draw in, cyan
  | "reveal-lines" // process lines + traveling light
  | "reveal-fusion" // tag↔bbox connectors snap
  | "evaluate-pulse" // anomaly pulse
  | "reveal-valves" // inline valves light up, orange
  | "stitch-graph" // connection graph completes
  | "metrics-countup"; // final KPIs count up

export interface StoryStep {
  id: string;
  no: number; // big step number on screen
  label: string; // KO headline
  sublabel: string; // KO one-liner
  agent: string; // which AWS/agent does this
  color: "cyan" | "amber" | "orange" | "violet" | "white";
  effect: EffectKind;
  /** target duration in ms (the replay clock scales these to fit ~30s) */
  ms: number;
}

/** The canonical 9-beat hook script. Order is fixed; data only tunes
 * which beats actually carry content (e.g. valves only on hierarchical). */
export const STORYBOARD: StoryStep[] = [
  { id: "render", no: 1, label: "도면 렌더링", sublabel: "PDF를 고해상도 이미지로 변환",
    agent: "pypdfium2", color: "white", effect: "scan-sweep", ms: 2200 },
  { id: "ocr", no: 2, label: "텍스트 인식 (OCR)", sublabel: "라벨·태그 좌표를 픽셀 단위로 추출",
    agent: "Amazon Textract", color: "cyan", effect: "ocr-flash", ms: 2600 },
  { id: "convention", no: 3, label: "표준 자동 판별", sublabel: "ISA-5.1 / DIN EN 10628 규격 감지",
    agent: "Convention Detector", color: "violet", effect: "badge-flip", ms: 2000 },
  { id: "vision", no: 4, label: "장비·계장 추출", sublabel: "Vision AI가 심볼과 관계를 인식",
    agent: "Claude Opus 4.8 Vision", color: "cyan", effect: "reveal-equipment", ms: 4200 },
  { id: "lines", no: 5, label: "배관 라인 추적", sublabel: "프로세스 라인 경로를 따라 연결 분석",
    agent: "Opus 4.8 · Line Refiner", color: "cyan", effect: "reveal-lines", ms: 3800 },
  { id: "fusion", no: 6, label: "좌표 정합 (Fusion)", sublabel: "Vision 태그 ↔ OCR 좌표 정밀 매칭",
    agent: "Strands Fusion", color: "cyan", effect: "reveal-fusion", ms: 2600 },
  { id: "valves", no: 7, label: "인라인 밸브 정밀 스캔", sublabel: "라인 위 작은 밸브 심볼까지 전수 검출",
    agent: "Opus 4.8 · Valve Scanner", color: "orange", effect: "reveal-valves", ms: 3200 },
  { id: "stitch", no: 8, label: "연결 관계 완성", sublabel: "누락된 connection을 추적해 그래프 완성",
    agent: "Opus 4.8 · Connection Stitcher", color: "amber", effect: "stitch-graph", ms: 2800 },
  { id: "finalize", no: 9, label: "분석 완료", sublabel: "검증 통과 · 결과 집계",
    agent: "Evaluator · Self-Correction", color: "white", effect: "metrics-countup", ms: 3000 },
];

/** Map a raw backend stage string to a storyboard step id. */
export function stageToStep(stage: string): string {
  if (stage === "render") return "render";
  if (stage.startsWith("ocr")) return "ocr";
  if (stage.startsWith("convention")) return "convention";
  if (stage === "extract" || stage.startsWith("zone")) return "vision";
  if (stage.startsWith("line")) return "lines";
  if (stage.startsWith("fusion")) return "fusion";
  if (stage.startsWith("valve")) return "valves";
  if (stage.startsWith("connection") || stage.startsWith("stitch")) return "stitch";
  // evaluate / self_correct / finalize all roll into the closing beat
  return "finalize";
}

/** Which storyboard steps actually have backing events in this drawing.
 * Steps with zero events still render (we keep the 9-beat rhythm) but we
 * use this to set realistic per-step detail counts. */
export function stepEventCounts(events: FrozenEvent[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const e of events) {
    const id = stageToStep(e.stage);
    counts[id] = (counts[id] ?? 0) + 1;
  }
  return counts;
}

/** Total nominal duration of the script (ms). */
export function storyboardDuration(): number {
  return STORYBOARD.reduce((sum, s) => sum + s.ms, 0);
}

/** Accent color token lookup for a step color. */
export const STEP_COLOR_VAR: Record<StoryStep["color"], string> = {
  cyan: "var(--accent)",
  amber: "#f59e0b",
  orange: "#f97316",
  violet: "#a78bfa",
  white: "#e2e8f0",
};
