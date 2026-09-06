import { motion } from "framer-motion";

export interface Bar {
  label: string;
  value: number;
  color?: string;
}

interface Props {
  title?: string;
  bars: Bar[];
  unit?: string;
}

/**
 * Lightweight animated horizontal bar chart (pure SVG/divs, no chart
 * lib). Used inside scripted chatbot answers to visualize category
 * counts (e.g. equipment-type distribution, object-kind totals).
 */
export function BarChart({ title, bars, unit = "개" }: Props) {
  if (bars.length === 0) {
    return (
      <div className="my-3 rounded-xl border border-border-default bg-canvas/40 px-4 py-3 text-sm text-fg-muted">
        {title ? `${title}: ` : ""}표시할 데이터가 없습니다
      </div>
    );
  }
  const max = Math.max(1, ...bars.map((b) => b.value));
  const palette = ["var(--accent)", "#f59e0b", "#f97316", "#a78bfa", "#34d399", "#60a5fa"];

  return (
    <div className="my-3 rounded-xl border border-border-default bg-canvas/40 px-4 py-3">
      {title && <div className="mb-3 text-sm font-semibold text-fg-secondary">{title}</div>}
      <div className="space-y-2.5">
        {bars.map((b, i) => {
          const pct = (b.value / max) * 100;
          const color = b.color ?? palette[i % palette.length];
          return (
            <div key={`${b.label}-${i}`} className="flex items-center gap-3">
              <div className="w-24 shrink-0 truncate text-right text-xs text-fg-muted">{b.label}</div>
              <div className="relative h-6 flex-1 overflow-hidden rounded-md bg-raised">
                <motion.div
                  className="absolute inset-y-0 left-0 rounded-md"
                  style={{ background: color, boxShadow: `0 0 12px color-mix(in srgb, ${color} 50%, transparent)` }}
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ delay: 0.1 + i * 0.08, duration: 0.6, ease: "easeOut" }}
                />
              </div>
              <div className="w-12 shrink-0 font-mono text-sm font-semibold" style={{ color }}>
                {b.value}
                <span className="ml-0.5 text-[10px] text-fg-muted">{unit}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
