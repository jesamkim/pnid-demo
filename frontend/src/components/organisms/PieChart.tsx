import { motion } from "framer-motion";

export interface Slice {
  label: string;
  value: number;
  color?: string;
}

interface Props {
  title?: string;
  slices: Slice[];
  unit?: string;
}

const PALETTE = ["var(--accent)", "#f59e0b", "#f97316", "#a78bfa", "#34d399", "#60a5fa", "#f472b6"];

function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function arc(cx: number, cy: number, r: number, start: number, end: number): string {
  const [sx, sy] = polar(cx, cy, r, end);
  const [ex, ey] = polar(cx, cy, r, start);
  const large = end - start <= 180 ? 0 : 1;
  return `M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey} Z`;
}

/**
 * Lightweight donut/pie chart (pure SVG) for proportion-style answers
 * inside the scripted chatbot. Slices animate in; legend lists shares.
 */
export function PieChart({ title, slices, unit = "개" }: Props) {
  const rawTotal = slices.reduce((s, x) => s + x.value, 0);
  if (slices.length === 0 || rawTotal <= 0) {
    return (
      <div className="my-3 rounded-xl border border-border-default bg-canvas/40 px-4 py-3 text-sm text-fg-muted">
        {title ? `${title}: ` : ""}표시할 데이터가 없습니다
      </div>
    );
  }
  const total = rawTotal;
  const cx = 70, cy = 70, r = 60;
  let acc = 0;
  const segs = slices.map((s, i) => {
    const start = (acc / total) * 360;
    acc += s.value;
    const end = (acc / total) * 360;
    return { ...s, start, end, color: s.color ?? PALETTE[i % PALETTE.length] };
  });

  return (
    <div className="my-3 rounded-xl border border-border-default bg-canvas/40 px-4 py-3">
      {title && <div className="mb-2 text-sm font-semibold text-fg-secondary">{title}</div>}
      <div className="flex items-center gap-4">
        <svg width={140} height={140} viewBox="0 0 140 140" className="shrink-0">
          {segs.map((s, i) => (
            <motion.path
              key={`${s.label}-${i}`}
              d={arc(cx, cy, r, s.start, s.end)}
              fill={s.color}
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.92 }}
              transition={{ delay: 0.1 + i * 0.1 }}
              stroke="var(--bg-surface)"
              strokeWidth={2}
            />
          ))}
          {/* donut hole */}
          <circle cx={cx} cy={cy} r={28} fill="var(--bg-surface)" />
          <text x={cx} y={cy - 2} textAnchor="middle" fill="var(--fg-primary)" fontSize={20} fontWeight="700" fontFamily="monospace">
            {total}
          </text>
          <text x={cx} y={cy + 14} textAnchor="middle" fill="var(--fg-muted)" fontSize={10}>
            {unit}
          </text>
        </svg>
        <div className="flex-1 space-y-1.5">
          {segs.map((s, i) => (
            <div key={`${s.label}-${i}`} className="flex items-center gap-2 text-sm">
              <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: s.color }} />
              <span className="flex-1 truncate text-fg-secondary">{s.label}</span>
              <span className="font-mono text-fg-primary">{s.value}</span>
              <span className="w-10 text-right text-xs text-fg-muted">
                {Math.round((s.value / total) * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
