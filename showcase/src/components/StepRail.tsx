import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { STORYBOARD, STEP_COLOR_VAR } from "../lib/storyboard";
import type { Convention } from "../lib/types";

interface Props {
  stepIndex: number;
  stepProgress: number;
  totalProgress: number;
  done: boolean;
  convention: Convention;
}

/**
 * Top rail — the 9 storyboard beats as a horizontal progress track.
 * Current beat pulses; completed beats get a check; a thin accent line
 * fills left-to-right with total progress.
 */
export function StepRail({ stepIndex, stepProgress, totalProgress, done, convention }: Props) {
  // The step circles are laid out with justify-between, so circle i sits
  // at i/(n-1) of the track — NOT at a time-proportional offset. Driving
  // the light off `totalProgress` (wall-clock) desyncs it from the
  // circles because beats have unequal durations. Map the light to the
  // SAME step-index space so the comet head always sits on the active
  // beat's circle.
  const n = STORYBOARD.length;
  const railFraction = done
    ? 1
    : Math.min(1, (stepIndex + stepProgress) / (n - 1));
  const railPct = railFraction * 100;
  return (
    <div className="relative z-20 border-b border-border-default bg-surface/70 px-8 py-4 backdrop-blur">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-fg-secondary">
            AWS Bedrock AgentCore · Multi-Agent 분석
          </span>
          <span
            className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
            style={{
              background:
                convention === "DIN EN 10628"
                  ? "color-mix(in srgb, #a78bfa 22%, transparent)"
                  : "color-mix(in srgb, var(--accent) 20%, transparent)",
              color: convention === "DIN EN 10628" ? "#c4b5fd" : "var(--accent)",
            }}
          >
            {convention}
          </span>
        </div>
        <span className="font-mono text-sm text-fg-muted">
          {done ? "완료" : `${Math.round(totalProgress * 100)}%`}
        </span>
      </div>

      {/* Track */}
      <div className="relative flex items-center justify-between">
        {/* base line */}
        <div className="absolute left-0 right-0 top-1/2 h-0.5 -translate-y-1/2 bg-border-default" />
        {/* progress line — gradient fill + animated flowing sheen.
            Width tracks step-index space so the leading edge lands on the
            active beat's circle. */}
        <div
          className="absolute left-0 top-1/2 h-1 -translate-y-1/2 overflow-hidden rounded-full transition-[width] duration-300"
          style={{
            width: `${railPct}%`,
            background:
              "linear-gradient(90deg, color-mix(in srgb, var(--accent) 35%, transparent), var(--accent))",
            boxShadow: "0 0 16px var(--accent), 0 0 4px var(--accent)",
          }}
        >
          {/* flowing sheen that travels along the filled portion */}
          {!done && (
            <div
              className="absolute inset-y-0 w-24"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.85), transparent)",
                animation: "sc-sweep 1.6s ease-in-out infinite",
              }}
            />
          )}
        </div>
        {/* glowing comet head at the leading edge of progress */}
        {!done && (
          <div
            className="absolute top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 transition-[left] duration-300"
            style={{ left: `${railPct}%` }}
          >
            <div
              className="h-3.5 w-3.5 rounded-full bg-white"
              style={{
                boxShadow:
                  "0 0 10px 3px var(--accent), 0 0 22px 8px color-mix(in srgb, var(--accent) 55%, transparent)",
                animation: "sc-glow-breathe 1s ease-in-out infinite",
              }}
            />
          </div>
        )}

        {STORYBOARD.map((s, i) => {
          const isDone = done || i < stepIndex;
          const isCurrent = !done && i === stepIndex;
          const color = STEP_COLOR_VAR[s.color];
          return (
            <div key={s.id} className="relative z-10 flex flex-col items-center">
              <motion.div
                className="flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-bold"
                animate={{
                  scale: isCurrent ? [1, 1.18, 1] : 1,
                  borderColor: isDone || isCurrent ? color : "var(--border-strong)",
                  backgroundColor: isDone
                    ? color
                    : isCurrent
                    ? "color-mix(in srgb, var(--accent) 18%, var(--bg-surface))"
                    : "var(--bg-surface)",
                  color: isDone ? "#06070b" : isCurrent ? color : "var(--fg-muted)",
                }}
                transition={{ duration: isCurrent ? 1.4 : 0.3, repeat: isCurrent ? Infinity : 0 }}
              >
                {isDone ? <Check size={18} strokeWidth={3} /> : s.no}
              </motion.div>
              <span
                className="mt-2 hidden max-w-[7rem] text-center text-xs leading-tight lg:block"
                style={{ color: isCurrent ? color : "var(--fg-muted)" }}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
