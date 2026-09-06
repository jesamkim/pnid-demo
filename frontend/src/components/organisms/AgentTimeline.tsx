/**
 * Agent timeline — vertical stepper showing pipeline progress events.
 *
 * Self-correct events are visually grouped into a nested block under
 * the parent `evaluate` step, with iteration counters surfaced when the
 * orchestrator reports them. The list also highlights the most recent
 * event when streaming live (Phase 3.4 hook integration).
 */
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/atoms/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/atoms/Card";
import { cn } from "@/lib/cn";
import { stageMeta, verdictLabel } from "@/lib/stages";
import type { ProgressEvent } from "@/api/types";

interface Props {
  events: ProgressEvent[];
  loading: boolean;
  totalElapsedS?: number | null;
  iterationsUsed?: number | null;
  finalVerdict?: string | null;
  /**
   * Index of the most recent event we should pulse. Used by the live
   * WebSocket mode in Phase 3.4 to draw attention to the current step.
   */
  liveCursor?: number | null;
}

export function AgentTimeline({
  events,
  loading,
  totalElapsedS,
  iterationsUsed,
  finalVerdict,
  liveCursor,
}: Props) {
  const groups = useMemo(() => groupEvents(events), [events]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Agent Timeline</CardTitle>
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          {iterationsUsed != null && iterationsUsed > 0 ? (
            <Badge tone="warning">iter {iterationsUsed}</Badge>
          ) : null}
          {finalVerdict ? (
            <Badge tone={finalVerdict === "pass" ? "success" : "warning"}>
              {verdictLabel(finalVerdict)}
            </Badge>
          ) : null}
          {totalElapsedS != null ? (
            <span>
              {events.length} events / {totalElapsedS.toFixed(1)}s
            </span>
          ) : null}
        </div>
      </CardHeader>
      <CardBody className="flex-1 overflow-y-auto">
        {loading ? (
          <p className="text-sm text-fg-muted">Loading pipeline…</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-fg-muted">
            Pick a drawing to see its agentic pipeline trace.
          </p>
        ) : (
          <ol className="flex flex-col gap-2" role="list">
            {groups.map((node) =>
              node.kind === "single" ? (
                <TimelineRow
                  key={`row-${node.index}`}
                  event={node.event}
                  index={node.index}
                  liveCursor={liveCursor}
                />
              ) : (
                <SelfCorrectGroup
                  key={`grp-${node.startIndex}`}
                  events={node.events}
                  startIndex={node.startIndex}
                  liveCursor={liveCursor}
                />
              ),
            )}
          </ol>
        )}
      </CardBody>
    </Card>
  );
}

/* -------- grouping ------------------------------------------------- */

interface SingleNode {
  kind: "single";
  index: number;
  event: ProgressEvent;
}
interface SelfCorrectNode {
  kind: "self_correct";
  startIndex: number;
  events: Array<{ index: number; event: ProgressEvent }>;
}
type Node = SingleNode | SelfCorrectNode;

function groupEvents(events: ProgressEvent[]): Node[] {
  const out: Node[] = [];
  let bucket: SelfCorrectNode | null = null;
  events.forEach((event, index) => {
    const meta = stageMeta(event.stage);
    if (meta.group === "self_correct") {
      if (!bucket) {
        bucket = { kind: "self_correct", startIndex: index, events: [] };
        out.push(bucket);
      }
      bucket.events.push({ index, event });
    } else {
      bucket = null;
      out.push({ kind: "single", index, event });
    }
  });
  return out;
}

/* -------- rows ----------------------------------------------------- */

interface RowProps {
  event: ProgressEvent;
  index: number;
  liveCursor?: number | null;
  indent?: boolean;
}

function TimelineRow({ event, index, liveCursor, indent }: RowProps) {
  const meta = stageMeta(event.stage);
  const isLive = liveCursor === index;
  return (
    <li
      className={cn(
        "flex gap-3 rounded-md p-2",
        isLive && "bg-[var(--accent-soft)]",
        indent && "ml-7",
      )}
    >
      <StageIcon icon={meta.icon} live={isLive} tone={meta.tone} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-fg-secondary">
            {meta.label}
          </span>
          <span className="text-xs text-fg-muted">
            {event.elapsed_s.toFixed(2)}s
          </span>
        </div>
        <p className="mt-0.5 break-words text-sm text-fg-primary">
          {event.detail}
        </p>
        <RowExtras event={event} />
      </div>
    </li>
  );
}

function RowExtras({ event }: { event: ProgressEvent }) {
  const extra = event.extra ?? {};
  const iteration = typeof extra.iteration === "number" ? extra.iteration : null;
  const verdictAfterRaw =
    typeof extra.verdict_after === "string" ? extra.verdict_after : null;
  const verdictAfter = verdictLabel(verdictAfterRaw);
  const inputTokens =
    typeof extra.input_tokens === "number" ? extra.input_tokens : null;
  const outputTokens =
    typeof extra.output_tokens === "number" ? extra.output_tokens : null;

  if (
    iteration == null &&
    verdictAfter == null &&
    inputTokens == null &&
    outputTokens == null
  ) {
    return null;
  }

  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {iteration != null ? <Badge tone="neutral">iter {iteration}</Badge> : null}
      {verdictAfter ? (
        <Badge tone={verdictAfterRaw === "pass" ? "success" : "warning"}>
          {verdictAfter}
        </Badge>
      ) : null}
      {inputTokens != null ? (
        <Badge tone="neutral">in {inputTokens.toLocaleString()}</Badge>
      ) : null}
      {outputTokens != null ? (
        <Badge tone="neutral">out {outputTokens.toLocaleString()}</Badge>
      ) : null}
    </div>
  );
}

interface SelfCorrectGroupProps {
  events: Array<{ index: number; event: ProgressEvent }>;
  startIndex: number;
  liveCursor?: number | null;
}

function SelfCorrectGroup({
  events,
  liveCursor,
}: SelfCorrectGroupProps) {
  const iterations = new Set<number>();
  for (const { event } of events) {
    const it = event.extra?.iteration;
    if (typeof it === "number" && it > 0) iterations.add(it);
  }
  const totalElapsed = events.reduce((s, { event }) => s + event.elapsed_s, 0);

  return (
    <li className="rounded-md border border-dashed border-warning/60 bg-[color-mix(in_oklab,var(--warning)_8%,transparent)] p-2">
      <div className="flex items-center justify-between gap-2 px-1 pb-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-warning">
          Self-correction loop
        </span>
        <div className="flex items-center gap-1.5 text-xs text-fg-muted">
          {iterations.size > 0 ? (
            <Badge tone="warning">
              {iterations.size} iter{iterations.size > 1 ? "s" : ""}
            </Badge>
          ) : (
            <Badge tone="neutral">no retry</Badge>
          )}
          <span>{totalElapsed.toFixed(1)}s</span>
        </div>
      </div>
      <ol className="flex flex-col gap-1.5" role="list">
        {events.map(({ event, index }) => (
          <TimelineRow
            key={`sc-${index}`}
            event={event}
            index={index}
            liveCursor={liveCursor}
            indent
          />
        ))}
      </ol>
    </li>
  );
}

function StageIcon({
  icon: Icon,
  live,
  tone,
}: {
  icon: LucideIcon;
  live: boolean;
  tone: "neutral" | "accent" | "success" | "warning" | "danger";
}) {
  const toneClass: Record<typeof tone, string> = {
    neutral: "bg-subtle text-fg-secondary",
    accent: "bg-[var(--accent-soft)] text-accent",
    success: "bg-[color-mix(in_oklab,var(--success)_20%,transparent)] text-success",
    warning: "bg-[color-mix(in_oklab,var(--warning)_20%,transparent)] text-warning",
    danger: "bg-[color-mix(in_oklab,var(--danger)_20%,transparent)] text-danger",
  };
  return (
    <motion.span
      aria-hidden
      className={cn(
        "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
        toneClass[tone],
      )}
      animate={live ? { scale: [1, 1.1, 1] } : undefined}
      transition={
        live ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" } : undefined
      }
    >
      <Icon size={15} />
    </motion.span>
  );
}

/* useMemo without importing the whole React namespace at the top of the file */
import { useMemo } from "react";
