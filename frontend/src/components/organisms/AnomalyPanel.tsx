import { AlertTriangle, MapPin, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/atoms/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/atoms/Card";
import { cn } from "@/lib/cn";
import type { Anomaly } from "@/api/types";

interface Props {
  anomalies: Anomaly[];
  loading: boolean;
  /** Called when the user clicks an anomaly's `violated_by` tag.
   * Optional — without it, the tag chip stays informational. */
  onSelectTag?: (tag: string) => void;
}

const severityToTone: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

export function AnomalyPanel({ anomalies, loading, onSelectTag }: Props) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>ISA-5.1 Anomalies</CardTitle>
        <Badge tone={anomalies.length > 0 ? "warning" : "success"}>
          {anomalies.length}
        </Badge>
      </CardHeader>
      <CardBody className="flex-1 overflow-y-auto">
        {loading ? (
          <p className="text-sm text-fg-muted">Loading…</p>
        ) : anomalies.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-fg-secondary">
            <ShieldCheck aria-hidden className="text-success" size={16} />
            No rule violations detected.
          </div>
        ) : (
          <ul className="flex flex-col gap-3" role="list">
            {anomalies.map((a, i) => (
              <li
                key={`${a.rule}-${a.violated_by}-${i}`}
                className="rounded-md border border-border-default bg-subtle p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-sm font-semibold text-fg-primary">
                    <AlertTriangle aria-hidden className="text-warning" size={14} />
                    {a.rule.replace(/_/g, " ")}
                  </div>
                  <Badge tone={severityToTone[a.severity] ?? "neutral"}>
                    {a.severity}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-fg-secondary">{a.description}</p>
                <button
                  type="button"
                  onClick={() => onSelectTag?.(a.violated_by)}
                  disabled={!onSelectTag}
                  aria-label={`Highlight ${a.violated_by} on the drawing`}
                  className={cn(
                    "mt-2 inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-mono",
                    onSelectTag
                      ? "border-border-default text-fg-secondary hover:border-warning hover:bg-[color-mix(in_oklab,var(--warning)_15%,transparent)] hover:text-fg-primary"
                      : "cursor-default border-border-default text-fg-muted",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  )}
                >
                  <MapPin aria-hidden size={11} />
                  {a.violated_by}
                </button>
                {a.suggestion ? (
                  <p className="mt-2 text-xs text-fg-secondary">
                    <span className="font-semibold text-fg-muted">suggestion: </span>
                    {a.suggestion}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
