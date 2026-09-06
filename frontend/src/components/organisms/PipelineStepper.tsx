/**
 * PipelineStepper — persistent horizontal progress indicator.
 *
 * Shows Steps 1–7 (plus sub-steps 6.5/6.7) as a compact rail at the
 * top of the viewer. Current step pulses; completed steps show a
 * checkmark. Idle state shows the rail dimmed. Much more informative
 * than the transient PnidStepBanner overlay it replaces visually.
 */
import { Check, Loader2 } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/cn";
import type { ProgressEvent } from "@/api/types";

const STEPS = [
  { id: 1, label: "Normalize", stages: ["render"] },
  { id: 2, label: "Vision", stages: ["extract"] },
  { id: 3, label: "OCR", stages: ["ocr_extract", "convention_detect"] },
  { id: 4, label: "Fusion", stages: ["line_refine", "fusion_done", "fusion_match_line", "fusion_match_instrument"] },
  { id: 5, label: "Evaluate", stages: ["evaluate"] },
  { id: 6, label: "Self-Correct", stages: ["self_correct", "self_correct_done", "self_correct_initial_extract", "self_correct_error_analysis", "self_correct_reextract", "self_correct_re_evaluate", "self_correct_hold"] },
  { id: 6.5, label: "Valves", stages: ["valve_scan"] },
  { id: 6.7, label: "Connections", stages: ["connection_stitch"] },
  { id: 7, label: "Index", stages: ["finalize"] },
] as const;

interface Props {
  events: ProgressEvent[];
  cursor: number | null;
  active: boolean;
  done: boolean;
}

function currentStepId(events: ProgressEvent[], cursor: number | null): number | null {
  if (cursor == null || cursor < 0 || !events[cursor]) return null;
  const stage = events[cursor].stage;
  for (const step of STEPS) {
    if (step.stages.some((s) => stage.startsWith(s))) return step.id;
  }
  return null;
}

function completedStepIds(events: ProgressEvent[], cursor: number | null): Set<number> {
  const set = new Set<number>();
  const limit = cursor != null ? cursor + 1 : events.length;
  for (let i = 0; i < limit; i++) {
    const stage = events[i]?.stage;
    if (!stage) continue;
    for (const step of STEPS) {
      if (step.stages.some((s) => stage.startsWith(s))) set.add(step.id);
    }
  }
  return set;
}

export function PipelineStepper({ events, cursor, active, done }: Props) {
  const current = active ? currentStepId(events, cursor) : null;
  const completed = done
    ? new Set(STEPS.map((s) => s.id))
    : completedStepIds(events, cursor);

  return (
    <div
      className={cn(
        "flex items-center gap-0.5 rounded-lg border px-2 py-1.5",
        "border-border-default bg-surface/80 backdrop-blur-sm",
        !active && !done && "opacity-40",
      )}
    >
      {STEPS.map((step, i) => {
        const isCurrent = current === step.id;
        const isCompleted = done || (completed.has(step.id) && !isCurrent);
        const isSubStep = step.id === 6.5 || step.id === 6.7;

        return (
          <div key={step.id} className="flex items-center">
            {i > 0 && (
              <div
                className={cn(
                  "mx-0.5 h-px w-2",
                  isCompleted ? "bg-accent" : "bg-border-default",
                )}
              />
            )}
            <div
              className={cn(
                "flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium leading-none transition-all",
                isSubStep && "text-[9px]",
                isCurrent && "bg-accent/20 text-accent",
                isCompleted && !isCurrent && "text-accent/70",
                !isCurrent && !isCompleted && "text-fg-muted",
              )}
            >
              <span
                className={cn(
                  "flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold",
                  isCurrent && "bg-accent text-canvas",
                  isCompleted && !isCurrent && "bg-accent/30 text-accent",
                  !isCurrent && !isCompleted && "bg-border-default text-fg-muted",
                )}
              >
                {isCompleted && !isCurrent ? (
                  <Check size={10} strokeWidth={3} />
                ) : isCurrent ? (
                  <motion.span
                    animate={{ opacity: [1, 0.4, 1] }}
                    transition={{ duration: 1.2, repeat: Infinity }}
                  >
                    <Loader2 size={10} className="animate-spin" />
                  </motion.span>
                ) : (
                  <span>{String(step.id)}</span>
                )}
              </span>
              <span className="hidden sm:inline">{step.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
