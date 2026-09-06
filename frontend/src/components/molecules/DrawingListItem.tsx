import { Files, ShieldAlert, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/atoms/Badge";
import { cn } from "@/lib/cn";
import type { DrawingSummary } from "@/api/types";

interface Props {
  drawing: DrawingSummary;
  selected: boolean;
  onSelect: (key: string) => void;
}

export function DrawingListItem({ drawing, selected, onSelect }: Props) {
  const isReal = drawing.kind === "real";
  // Real samples have no GT, so verdict + counts would be misleading.
  const showMetrics = drawing.has_ground_truth !== false && !isReal;
  const verdictTone =
    drawing.verdict === "pass"
      ? "success"
      : drawing.verdict === "needs_correction"
        ? "warning"
        : "neutral";
  const VerdictIcon = drawing.verdict === "pass" ? ShieldCheck : ShieldAlert;

  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={`Select drawing ${drawing.key}, verdict ${drawing.verdict ?? "live only"}`}
      onClick={() => onSelect(drawing.key)}
      className={cn(
        "group w-full rounded-md border px-3 py-3 text-left transition-all " +
          "duration-[var(--motion-base)] focus-visible:outline-2 " +
          "focus-visible:outline-offset-2 focus-visible:outline-accent",
        selected
          ? "border-accent bg-[var(--accent-soft)] shadow-[var(--shadow-glow)]"
          : "border-border-default bg-surface hover:border-accent/40 " +
            "hover:bg-raised hover:shadow-[0_0_18px_var(--accent-soft)]",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-semibold text-fg-primary">
          <Files aria-hidden size={14} className="text-fg-muted" />
          <span>{drawing.key}</span>
        </div>
        {showMetrics ? (
          <Badge tone={verdictTone}>
            <VerdictIcon aria-hidden size={11} />
            {drawing.verdict}
          </Badge>
        ) : (
          <Badge tone="neutral">live</Badge>
        )}
      </div>
      <p className="mt-1 truncate text-xs text-fg-muted">{drawing.pdf}</p>
      {showMetrics ? (
        <dl className="mt-3 grid grid-cols-4 gap-1 text-[10px] uppercase tracking-wide text-fg-muted">
          <Stat label="Eq" value={drawing.counts.equipment} />
          <Stat label="Inst" value={drawing.counts.instruments} />
          <Stat label="Lines" value={drawing.counts.lines} />
          <Stat label="Anom" value={drawing.counts.anomalies} highlight={drawing.counts.anomalies > 0} />
        </dl>
      ) : drawing.source ? (
        <p
          className="mt-2 text-[10px] leading-tight text-fg-muted"
          title={drawing.source}
        >
          {drawing.source}
        </p>
      ) : null}
    </button>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <dt>{label}</dt>
      <dd
        className={cn(
          "text-base font-semibold normal-case tracking-normal",
          highlight ? "text-warning" : "text-fg-primary",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
