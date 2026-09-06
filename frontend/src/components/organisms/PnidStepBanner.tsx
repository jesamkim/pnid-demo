/**
 * PnidStepBanner — animated stage banner overlaid on the drawing.
 *
 * Subscribes to whichever state machine is currently driving the
 * extraction (replay or live stream). Shows a transient banner per
 * stage with smooth slide+fade transitions; honours
 * `prefers-reduced-motion` by dropping the slide while keeping the
 * opacity fade.
 *
 * Stage map (matches backend orchestrator events):
 *   render               → "Step 1 — Rendering page"
 *   extract              → "Step 2 — Vision agent detecting objects"
 *   ocr_extract          → "Step 3 — OCR agent locating tags"
 *   fusion_*             → "Step 4 — Fusion agent matching coordinates"
 *   evaluate             → "Step 5 — ISA-5.1 rule check"
 *   self_correct_*       → "Step 6 — Self-correction loop"
 *   finalize             → "Step 7 — Finalizing"
 *   (auto, after `done`) → "Analysis complete"
 *
 * Dismiss behaviour:
 *   - The banner is dismissable: click anywhere on the card (or the
 *     × icon) and it disappears immediately. A new Run resets the
 *     dismissed state automatically.
 *   - When the run finishes (`done`), the banner auto-hides after
 *     a short delay too — but the user-clickable dismiss is the
 *     definitive escape hatch when the auto-hide misses an edge case.
 */
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ProgressEvent } from "@/api/types";

interface Props {
  events: ProgressEvent[];
  cursor: number | null;
  active: boolean;
  done: boolean;
  /** When true the parent already provides the absolute positioning
   * wrapper; the banner only renders the motion card itself. */
  standalone?: boolean;
}

interface StageView {
  step: number;
  title: string;
  detail: string;
}

export function PnidStepBanner({ events, cursor, active, done, standalone = false }: Props) {
  const reduceMotion = useReducedMotion() ?? false;
  const view = useMemo(() => deriveStage(events, cursor, done), [events, cursor, done]);
  const [showFinal, setShowFinal] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // Reset the dismissed state any time a new run starts (active flips
  // back on, or the cursor restarts at 0). This means clicking the
  // banner closed during one run does NOT keep it hidden forever.
  const prevActiveRef = useRef(active);
  useEffect(() => {
    if (active && !prevActiveRef.current) {
      setDismissed(false);
    }
    prevActiveRef.current = active;
  }, [active]);

  useEffect(() => {
    if (done && !showFinal) {
      setShowFinal(true);
      const t = window.setTimeout(() => setShowFinal(false), 2200);
      return () => window.clearTimeout(t);
    }
    if (!done) setShowFinal(false);
    return undefined;
  }, [done, showFinal]);

  if (dismissed) return null;
  if (!active && !showFinal) return null;
  if (!view && !showFinal) return null;

  const banner = showFinal && done
    ? { step: 7, title: "Analysis complete", detail: "All stages finished" }
    : view;
  if (!banner) return null;

  const inner = (
    <AnimatePresence mode="popLayout">
      <motion.div
        key={`${banner.step}-${banner.title}`}
        initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -22, scale: 0.96 }}
        animate={reduceMotion
          ? { opacity: 1 }
          : { opacity: 1, y: 0, scale: 1 }}
        exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -14, scale: 0.97 }}
        transition={reduceMotion
          ? { duration: 0.18 }
          : { type: "spring", stiffness: 320, damping: 28, mass: 0.85 }}
        // pointer-events-auto so the click-to-dismiss works even though
        // the parent wrapper is pointer-events-none.
        className="pointer-events-auto group relative cursor-pointer rounded-xl border border-accent/50 bg-[var(--bg-surface)]/85 px-5 py-3 pr-9 shadow-[var(--shadow-glow)] backdrop-blur-md ring-1 ring-[var(--accent-glow)]"
        style={{ minWidth: 360, maxWidth: 720 }}
        role="status"
        aria-label={`${banner.title}. Click to dismiss.`}
        onClick={() => setDismissed(true)}
      >
        <div className="text-[10px] font-semibold uppercase tracking-wider text-accent">
          Step {banner.step} of 7
        </div>
        <div className="mt-0.5 text-sm font-semibold text-fg-primary">
          {banner.title}
        </div>
        <div
          className="mt-1 truncate text-xs text-fg-secondary"
          title={banner.detail}
        >
          {banner.detail}
        </div>
        <button
          type="button"
          aria-label="Dismiss step banner"
          onClick={(e) => {
            e.stopPropagation();
            setDismissed(true);
          }}
          className="absolute right-2 top-2 rounded p-1 text-fg-muted opacity-0 transition group-hover:opacity-100 hover:bg-accent/10 hover:text-accent focus-visible:opacity-100"
        >
          <X aria-hidden size={14} />
        </button>
      </motion.div>
    </AnimatePresence>
  );

  if (standalone) return inner;
  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-30 flex justify-center">
      {inner}
    </div>
  );
}

function deriveStage(
  events: ProgressEvent[],
  cursor: number | null,
  done: boolean,
): StageView | null {
  if (cursor == null || cursor < 0) return null;
  const ev = events[Math.max(0, Math.min(cursor, events.length - 1))];
  if (!ev) return null;
  const stage = ev.stage;
  const detail = ev.detail || "";
  if (stage === "render") {
    return { step: 1, title: "Rendering page at 200 dpi", detail };
  }
  if (stage === "extract") {
    return { step: 2, title: "Vision agent detecting equipment & instruments", detail };
  }
  if (stage === "ocr_extract") {
    return { step: 3, title: "OCR agent locating tags", detail };
  }
  if (stage.startsWith("fusion_")) {
    return { step: 4, title: "Fusion agent matching tags to coordinates", detail };
  }
  if (stage === "evaluate") {
    return { step: 5, title: "ISA-5.1 rule check", detail };
  }
  if (stage.startsWith("self_correct_")) {
    const iteration = (ev.extra && typeof (ev.extra as any).iteration === "number")
      ? (ev.extra as any).iteration
      : null;
    const suffix = iteration ? ` (iteration ${iteration})` : "";
    return {
      step: 6,
      title: `Self-correction loop${suffix}`,
      detail,
    };
  }
  if (stage === "finalize") {
    return { step: 7, title: "Finalizing", detail };
  }
  if (done) {
    return { step: 7, title: "Analysis complete", detail: "All stages finished" };
  }
  return null;
}
