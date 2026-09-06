/**
 * MetricCards — bold stat display after extraction completes.
 *
 * Shows Equipment / Instruments / Connections / Lines as large animated
 * numbers with category-colored icons. Replaces cramped text stats with
 * a dashboard-style overview that's readable at a glance.
 */
import { useEffect, useRef, useState } from "react";
import { Box, Gauge, GitBranch, Minus } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/cn";
import type { PipelineDump } from "@/api/types";

interface Props {
  result: PipelineDump | null;
}

const METRICS = [
  { key: "equipment", label: "Equipment", icon: Box, color: "text-[#00d4ff]", bg: "bg-[#00d4ff]/10" },
  { key: "instruments", label: "Instruments", icon: Gauge, color: "text-[#f59e0b]", bg: "bg-[#f59e0b]/10" },
  { key: "connections", label: "Connections", icon: GitBranch, color: "text-[#f97316]", bg: "bg-[#f97316]/10" },
  { key: "lines", label: "Lines", icon: Minus, color: "text-[#64748b]", bg: "bg-[#64748b]/10" },
] as const;

function useCountUp(target: number, duration = 800) {
  const [value, setValue] = useState(0);
  const prevTarget = useRef(0);

  useEffect(() => {
    if (target === prevTarget.current) return;
    prevTarget.current = target;
    const start = performance.now();
    const from = 0;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
  delay,
}: {
  label: string;
  value: number;
  icon: typeof Box;
  color: string;
  bg: string;
  delay: number;
}) {
  const displayed = useCountUp(value);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
      className={cn(
        "flex items-center gap-3 rounded-lg border border-border-default",
        "bg-surface px-3 py-2 shadow-sm",
      )}
    >
      <div className={cn("flex h-8 w-8 items-center justify-center rounded-md", bg)}>
        <Icon size={16} className={color} />
      </div>
      <div className="flex flex-col">
        <span className="text-lg font-bold tabular-nums text-fg-primary">
          {displayed}
        </span>
        <span className="text-[10px] uppercase tracking-wide text-fg-muted">
          {label}
        </span>
      </div>
    </motion.div>
  );
}

export function MetricCards({ result }: Props) {
  if (!result) return null;

  const counts = {
    equipment: result.extraction.equipment.length,
    instruments: result.extraction.instruments.length,
    connections: result.extraction.connections.length,
    lines: result.extraction.lines.length,
  };

  return (
    <div className="grid grid-cols-4 gap-2">
      {METRICS.map((m, i) => (
        <StatCard
          key={m.key}
          label={m.label}
          value={counts[m.key]}
          icon={m.icon}
          color={m.color}
          bg={m.bg}
          delay={i * 0.08}
        />
      ))}
    </div>
  );
}
