/**
 * Derive a bar chart for a scripted Q&A answer, when the question is
 * about counts / distribution. The chart is computed from the frozen
 * `extraction` (not parsed from the answer text), so it always matches
 * the data the pipeline produced.
 *
 * Returns null when the question doesn't call for a chart.
 */
import type { Bar } from "../components/BarChart";
import type { ExtractionRecord } from "./types";

const VALVE_TYPES = new Set([
  "gate_valve", "ball_valve", "control_valve", "check_valve", "safety_valve",
]);

const TYPE_KO: Record<string, string> = {
  gate_valve: "게이트밸브", ball_valve: "볼밸브", control_valve: "컨트롤밸브",
  check_valve: "체크밸브", safety_valve: "안전밸브", vessel: "용기",
  column: "컬럼", tank: "탱크", pump: "펌프", heat_exchanger: "열교환기",
  compressor: "압축기", vacuum_unit: "진공유닛", psv: "안전밸브(PSV)",
  air_cooler: "공랭식 냉각기", furnace: "가열로", reactor: "반응기",
  drum: "드럼", other: "기타",
};

function ko(type: string): string {
  return TYPE_KO[type] ?? type;
}

export interface ChartSpec {
  kind: "bar" | "pie";
  title: string;
  bars: Bar[]; // also used as pie slices (same {label,value,color} shape)
  unit?: string;
}

export function chartForQuestion(
  question: string,
  ex: ExtractionRecord,
): ChartSpec | null {
  const q = question;

  const valves = (ex.equipment ?? []).filter((e) => e.type && VALVE_TYPES.has(e.type));

  // 1) Valve-type distribution.
  if (q.includes("밸브") && (q.includes("종류") || q.includes("어떤"))) {
    const counts: Record<string, number> = {};
    for (const v of valves) counts[v.type!] = (counts[v.type!] ?? 0) + 1;
    const bars = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([t, n]) => ({ label: ko(t) + " 밸브", value: n }));
    if (bars.length) return { kind: "pie", title: "밸브 종류별 분포", bars };
  }

  // 2) Overall object-kind totals (equipment / valve / instrument / line).
  if (
    (q.includes("전체") || q.includes("검출")) &&
    (q.includes("장비") || q.includes("계장") || q.includes("밸브"))
  ) {
    // "장비" counts ALL equipment (incl. valves/PSV) so it matches the
    // metric card exactly. Valves shown as a sub-breakdown only when the
    // drawing actually has separate valve symbols.
    const bars: Bar[] = [
      { label: "장비", value: (ex.equipment ?? []).length },
      { label: "계장", value: (ex.instruments ?? []).length },
      { label: "라인", value: (ex.lines ?? []).length },
      { label: "연결", value: (ex.connections ?? []).length },
    ];
    if (valves.length) bars.splice(1, 0, { label: "밸브", value: valves.length });
    return { kind: "bar", title: "객체 종류별 검출 수", bars };
  }

  // 3) Equipment-type distribution ("어떤 주요 장비").
  // Count EVERY equipment type (no slice) so the pie total equals the
  // "장비" metric — a truncated top-N made the totals look inconsistent.
  if (q.includes("장비") && (q.includes("주요") || q.includes("어떤") || q.includes("핵심"))) {
    const counts: Record<string, number> = {};
    for (const e of ex.equipment ?? []) if (e.type) counts[e.type] = (counts[e.type] ?? 0) + 1;
    const bars = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([t, n]) => ({ label: ko(t), value: n }));
    if (bars.length) return { kind: "pie", title: "장비 유형 분포", bars };
  }

  return null;
}
