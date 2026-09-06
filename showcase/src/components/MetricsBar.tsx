import { useEffect, useState } from "react";
import { Boxes, Gauge, Spline, Workflow } from "lucide-react";
import type { Metrics } from "../lib/types";

interface Props {
  metrics: Metrics;
  active: boolean; // start counting up when true
}

const CARDS: Array<{
  key: keyof Metrics;
  label: string;
  icon: typeof Boxes;
  color: string;
}> = [
  { key: "equipment", label: "장비", icon: Boxes, color: "var(--accent)" },
  { key: "instruments", label: "계장", icon: Gauge, color: "#f59e0b" },
  { key: "lines", label: "배관 라인", icon: Spline, color: "#64748b" },
  { key: "connections", label: "연결 관계", icon: Workflow, color: "#a78bfa" },
];

function useCountUp(target: number, run: boolean, ms = 1200): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) {
      setV(0);
      return;
    }
    let raf = 0;
    let start: number | null = null;
    const tick = (t: number) => {
      if (start === null) start = t;
      const p = Math.min(1, (t - start) / ms);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - p, 3);
      setV(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, run, ms]);
  return v;
}

function Card({ card, value, run }: { card: (typeof CARDS)[number]; value: number; run: boolean }) {
  const display = useCountUp(value, run);
  const Icon = card.icon;
  return (
    <div
      className="flex items-center gap-4 rounded-2xl border border-border-default bg-surface/70 px-6 py-4 backdrop-blur transition-all"
      style={{
        borderColor: run ? `color-mix(in srgb, ${card.color} 45%, transparent)` : undefined,
        boxShadow: run ? `0 0 24px color-mix(in srgb, ${card.color} 18%, transparent)` : undefined,
      }}
    >
      <div
        className="flex h-12 w-12 items-center justify-center rounded-xl"
        style={{ background: `color-mix(in srgb, ${card.color} 16%, transparent)`, color: card.color }}
      >
        <Icon size={24} />
      </div>
      <div>
        <div className="font-mono text-3xl font-bold tabular-nums" style={{ color: card.color }}>
          {display}
        </div>
        <div className="text-sm text-fg-muted">{card.label}</div>
      </div>
    </div>
  );
}

export function MetricsBar({ metrics, active }: Props) {
  return (
    <div className="z-20 grid grid-cols-4 gap-4 border-t border-border-default bg-surface/60 px-8 py-5 backdrop-blur">
      {CARDS.map((c) => (
        <Card key={c.key} card={c} value={metrics[c.key]} run={active} />
      ))}
    </div>
  );
}
