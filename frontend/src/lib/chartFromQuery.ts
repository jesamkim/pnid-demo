/**
 * Derive a bar/pie chart for an NL-query answer when the question is
 * about counts / distribution. Computed from the current drawing's
 * geometry (same data the overlay uses), never parsed from the answer
 * prose — so the chart always matches what's on screen.
 *
 * Returns null when the question doesn't call for a chart.
 */
import type { Bar } from "@/components/organisms/BarChart";
import type { GeometryResponse } from "@/api/types";

const VALVE_TYPES = new Set([
  "gate_valve", "ball_valve", "control_valve", "check_valve", "safety_valve",
]);

const TYPE_KO: Record<string, string> = {
  gate_valve: "게이트", ball_valve: "볼", control_valve: "컨트롤",
  check_valve: "체크", safety_valve: "안전", vessel: "용기",
  column: "컬럼", tank: "탱크", pump: "펌프", heat_exchanger: "열교환기",
  compressor: "압축기", vacuum_unit: "진공유닛", drum: "드럼", reactor: "반응기",
};

const ko = (t: string) => TYPE_KO[t] ?? t;

export interface ChartSpec {
  kind: "bar" | "pie";
  title: string;
  bars: Bar[];
  unit?: string;
}

export function chartForQuery(
  question: string,
  geometry: GeometryResponse | null,
): ChartSpec | null {
  if (!geometry) return null;
  const q = question;

  const valves = geometry.equipment.filter((e) => e.type && VALVE_TYPES.has(e.type));

  // Valve-type distribution → pie.
  if (q.includes("밸브") && (q.includes("종류") || q.includes("어떤") || q.includes("무슨"))) {
    const counts: Record<string, number> = {};
    for (const v of valves) counts[v.type!] = (counts[v.type!] ?? 0) + 1;
    const bars = Object.entries(counts).sort((a, b) => b[1] - a[1])
      .map(([t, n]) => ({ label: ko(t) + " 밸브", value: n }));
    if (bars.length) return { kind: "pie", title: "밸브 종류별 분포", bars };
  }

  // Object-kind totals → bar.
  if (
    (q.includes("전체") || q.includes("검출") || q.includes("총") || q.includes("몇")) &&
    (q.includes("장비") || q.includes("계장") || q.includes("밸브") || q.includes("객체"))
  ) {
    // "장비" counts ALL equipment (incl. valves/PSV) to match the
    // metric card; valves shown as a sub-bar only when present.
    const bars: Bar[] = [
      { label: "장비", value: geometry.equipment.length },
      { label: "계장", value: geometry.instruments.length },
      { label: "라인", value: geometry.lines.length },
    ];
    if (valves.length) bars.splice(1, 0, { label: "밸브", value: valves.length });
    return { kind: "bar", title: "객체 종류별 검출 수", bars };
  }

  // Equipment-type distribution → pie. Count EVERY type (no slice) so the
  // total equals the "장비" metric.
  if (q.includes("장비") && (q.includes("주요") || q.includes("어떤") || q.includes("핵심") || q.includes("종류"))) {
    const counts: Record<string, number> = {};
    for (const e of geometry.equipment) if (e.type) counts[e.type] = (counts[e.type] ?? 0) + 1;
    const bars = Object.entries(counts).sort((a, b) => b[1] - a[1])
      .map(([t, n]) => ({ label: ko(t), value: n }));
    if (bars.length) return { kind: "pie", title: "장비 유형 분포", bars };
  }

  return null;
}
