/**
 * usePipelineReplay — drives a *cached* pipeline replay so the UI can
 * dramatize extraction without spending Bedrock tokens.
 *
 * Each cached event has a real `elapsed_s` from the original Strands
 * run; we collapse that timeline by `pace` (default 3×) and schedule
 * setTimeouts to fire each event in order. Pause/resume preserves the
 * remaining time on the in-flight event.
 *
 * Phase mapping (extract → evaluate → self_correct → finalize) is
 * derived from each event's `stage`, so consumers (PnidOverlay) can
 * decide which objects to fade in.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import type { ProgressEvent } from "@/api/types";

export type ReplayPhase =
  | "idle"
  | "extracting"
  | "evaluating"
  | "self_correcting"
  | "finalizing"
  | "done";

export type ReplayStatus = "idle" | "playing" | "paused" | "done";

export interface ReplayState {
  status: ReplayStatus;
  phase: ReplayPhase;
  cursor: number; // index of the most recent event fired, or -1 when idle
  elapsedMs: number; // virtual elapsed time within the current run
}

const INITIAL: ReplayState = {
  status: "idle",
  phase: "idle",
  cursor: -1,
  elapsedMs: 0,
};

export function stagePhase(stage: string): ReplayPhase {
  if (stage === "render") return "extracting";
  if (stage === "extract") return "extracting";
  if (stage === "evaluate") return "evaluating";
  if (stage.startsWith("self_correct_done")) return "finalizing";
  if (stage.startsWith("self_correct")) return "self_correcting";
  if (stage === "finalize") return "finalizing";
  return "idle";
}

export interface UsePipelineReplay {
  status: ReplayStatus;
  phase: ReplayPhase;
  cursor: number;
  elapsedMs: number;
  start: (events: ProgressEvent[]) => void;
  pause: () => void;
  resume: () => void;
  reset: () => void;
}

export function usePipelineReplay(pace: number = 3): UsePipelineReplay {
  const [state, setState] = useState<ReplayState>(INITIAL);
  const eventsRef = useRef<ProgressEvent[]>([]);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const startedAtRef = useRef<number>(0);
  const pausedAtRef = useRef<number | null>(null);
  // On pause we record, per unfired event, both the relative delay to
  // re-arm the timer AND its absolute virtual fire time (fireAtMs) so the
  // resumed event reports the correct `elapsedMs` to fireUntil.
  const remainingRef = useRef<{ idx: number; delayMs: number; fireAtMs: number }[] | null>(null);

  const clearTimers = () => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  };

  const fireUntil = useCallback(
    (idx: number, when: number) => {
      const ev = eventsRef.current[idx];
      if (!ev) return;
      const phase = stagePhase(ev.stage);
      setState({
        status: "playing",
        phase,
        cursor: idx,
        elapsedMs: when,
      });
      if (idx === eventsRef.current.length - 1) {
        // Tail timer marks completion shortly after the last event.
        timersRef.current.push(
          setTimeout(() => {
            setState((s) => ({ ...s, status: "done", phase: "done" }));
          }, 250),
        );
      }
    },
    [],
  );

  const start = useCallback(
    (events: ProgressEvent[]) => {
      clearTimers();
      eventsRef.current = events;
      pausedAtRef.current = null;
      remainingRef.current = null;
      if (!events.length) {
        setState({ ...INITIAL, status: "done", phase: "done" });
        return;
      }
      // Schedule each event at its cumulative virtual elapsed time.
      let cumMs = 0;
      const schedule: { idx: number; delayMs: number }[] = [];
      for (let i = 0; i < events.length; i++) {
        cumMs += Math.max(0, events[i]!.elapsed_s) * 1000;
        schedule.push({ idx: i, delayMs: cumMs / pace });
      }
      startedAtRef.current = Date.now();
      setState({ status: "playing", phase: stagePhase(events[0]!.stage), cursor: -1, elapsedMs: 0 });
      schedule.forEach(({ idx, delayMs }) => {
        timersRef.current.push(setTimeout(() => fireUntil(idx, delayMs), delayMs));
      });
    },
    [pace, fireUntil],
  );

  const pause = useCallback(() => {
    if (state.status !== "playing") return;
    pausedAtRef.current = Date.now();
    const elapsed = pausedAtRef.current - startedAtRef.current;
    // Compute remaining schedule for unfired events.
    let cumMs = 0;
    const remaining: { idx: number; delayMs: number; fireAtMs: number }[] = [];
    for (let i = 0; i < eventsRef.current.length; i++) {
      cumMs += Math.max(0, eventsRef.current[i]!.elapsed_s) * 1000;
      const fireAt = cumMs / pace; // absolute virtual fire time
      if (fireAt > elapsed) {
        remaining.push({ idx: i, delayMs: fireAt - elapsed, fireAtMs: fireAt });
      }
    }
    remainingRef.current = remaining;
    clearTimers();
    setState((s) => ({ ...s, status: "paused" }));
  }, [pace, state.status]);

  const resume = useCallback(() => {
    if (state.status !== "paused" || !remainingRef.current) return;
    const baseElapsed = state.elapsedMs;
    startedAtRef.current = Date.now() - baseElapsed;
    remainingRef.current.forEach(({ idx, delayMs, fireAtMs }) => {
      // Re-arm with the relative delay, but report the event's ABSOLUTE
      // virtual time so elapsedMs stays correct after a pause.
      timersRef.current.push(
        setTimeout(() => fireUntil(idx, fireAtMs), delayMs),
      );
    });
    pausedAtRef.current = null;
    remainingRef.current = null;
    setState((s) => ({ ...s, status: "playing" }));
  }, [fireUntil, state.elapsedMs, state.status]);

  const reset = useCallback(() => {
    clearTimers();
    eventsRef.current = [];
    pausedAtRef.current = null;
    remainingRef.current = null;
    setState(INITIAL);
  }, []);

  // Cleanup on unmount.
  useEffect(() => {
    return () => clearTimers();
  }, []);

  return {
    status: state.status,
    phase: state.phase,
    cursor: state.cursor,
    elapsedMs: state.elapsedMs,
    start,
    pause,
    resume,
    reset,
  };
}
