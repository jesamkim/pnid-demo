import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { ShowcaseDrawing } from "../lib/types";
import { STORYBOARD } from "../lib/storyboard";
import { useReplayClock } from "../lib/useReplayClock";
import { imageUrl, conventionFor } from "../lib/data";
import { CinematicOverlay } from "../components/CinematicOverlay";
import { StepRail } from "../components/StepRail";
import { MetricsBar } from "../components/MetricsBar";
import { HookChatbot } from "../components/HookChatbot";

interface Props {
  drawing: ShowcaseDrawing;
  onRestart: () => void;
}

/**
 * REPLAY — the cinematic core. A wall clock walks the 9-beat storyboard;
 * the overlay lights up the matching geometry; the step rail and the
 * scanning glow track progress. When the clock finishes, the hook
 * chatbot slides in.
 */
export function ReplayScreen({ drawing, onRestart }: Props) {
  const clock = useReplayClock({ speed: 1, autostart: true });
  const step = STORYBOARD[clock.stepIndex];
  const conv = conventionFor(drawing.drawing_id);

  // Track which beats have completed (their elements stay lit).
  const completedStepIds = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i < clock.stepIndex; i++) s.add(STORYBOARD[i].id);
    if (clock.done) s.add(STORYBOARD[STORYBOARD.length - 1].id);
    return s;
  }, [clock.stepIndex, clock.done]);

  // Reveal the chatbot a beat after the clock finishes.
  const [chatOpen, setChatOpen] = useState(false);
  useEffect(() => {
    if (clock.done) {
      const t = window.setTimeout(() => setChatOpen(true), 900);
      return () => window.clearTimeout(t);
    }
  }, [clock.done]);

  const analyzing = !clock.done;

  return (
    <motion.div
      className="absolute inset-0 flex flex-col"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Top step rail */}
      <StepRail
        stepIndex={clock.stepIndex}
        stepProgress={clock.stepProgress}
        totalProgress={clock.totalProgress}
        done={clock.done}
        convention={conv}
      />

      {/* Drawing stage */}
      <div className="relative flex-1 overflow-hidden">
        {/* The drawing itself — desaturated until vision begins, then full color */}
        <motion.div
          className="absolute inset-0 flex items-center justify-center p-6"
          animate={{
            filter: completedStepIds.has("render")
              ? "grayscale(0) brightness(1)"
              : "grayscale(0.85) brightness(0.7)",
          }}
          transition={{ duration: 1.2 }}
        >
          <div className="relative max-h-full max-w-full">
            <img
              src={imageUrl(drawing.image)}
              alt=""
              className="max-h-[68vh] w-auto rounded-lg"
              style={{ boxShadow: "0 0 80px color-mix(in srgb, var(--accent) 12%, transparent)" }}
            />
            {/* Overlay scaled to the image box */}
            <div className="absolute inset-0">
              <CinematicOverlay
                geometry={drawing.geometry}
                canvas={drawing.canvas}
                step={step}
                stepProgress={clock.stepProgress}
                completedStepIds={completedStepIds}
              />
            </div>

            {/* Scanning sweep during the render beat */}
            {step.id === "render" && analyzing && (
              <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg">
                <div
                  className="absolute inset-y-0 w-1/3"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent, color-mix(in srgb, var(--accent) 35%, transparent), transparent)",
                    animation: "sc-sweep 2.2s ease-in-out infinite",
                  }}
                />
              </div>
            )}
          </div>
        </motion.div>

        {/* Analyzing dim veil (subtle) */}
        {analyzing && (
          <div className="pointer-events-none absolute inset-0 bg-black/20" />
        )}

        {/* Current-beat caption card, bottom-left */}
        <motion.div
          key={step.id}
          className="absolute bottom-6 left-6 max-w-md rounded-2xl border border-border-strong bg-surface/80 px-6 py-5 backdrop-blur"
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
        >
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-full text-lg font-bold"
              style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
            >
              {step.no}
            </div>
            <div>
              <div className="text-xl font-bold">{step.label}</div>
              <div className="text-sm text-fg-muted">{step.agent}</div>
            </div>
          </div>
          <p className="mt-3 text-fg-secondary">{step.sublabel}</p>
        </motion.div>
      </div>

      {/* Bottom metrics — count up on the final beat */}
      <MetricsBar metrics={drawing.metrics} active={clock.done} />

      {/* Post-analysis hook chatbot */}
      <HookChatbot
        open={chatOpen}
        qa={drawing.qa}
        summary={drawing.summary}
        extraction={drawing.extraction}
        onClose={() => setChatOpen(false)}
        onRestart={onRestart}
      />
    </motion.div>
  );
}
