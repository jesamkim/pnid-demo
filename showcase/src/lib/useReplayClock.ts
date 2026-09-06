import { useEffect, useRef, useState } from "react";
import { STORYBOARD } from "./storyboard";

export interface ClockState {
  /** index into STORYBOARD of the current beat */
  stepIndex: number;
  /** 0..1 progress within the current beat */
  stepProgress: number;
  /** 0..1 progress across the whole script */
  totalProgress: number;
  /** true once the final beat has finished */
  done: boolean;
}

/**
 * Drives the storyboard on a wall clock using requestAnimationFrame.
 * `speed` scales every beat's nominal duration (1 = as authored). The
 * whole thing is deterministic and pure-frontend — no data dependency.
 *
 * Returns the live clock state plus a `restart()` to replay from 0.
 */
export function useReplayClock(opts: { speed?: number; autostart?: boolean } = {}) {
  const speed = opts.speed ?? 1;
  const [state, setState] = useState<ClockState>({
    stepIndex: 0,
    stepProgress: 0,
    totalProgress: 0,
    done: false,
  });
  const startRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const runningRef = useRef(opts.autostart ?? true);

  // Precompute scaled cumulative offsets.
  const durations = STORYBOARD.map((s) => s.ms / speed);
  const total = durations.reduce((a, b) => a + b, 0);
  const offsets: number[] = [];
  durations.reduce((acc, d, i) => {
    offsets[i] = acc;
    return acc + d;
  }, 0);

  useEffect(() => {
    function frame(now: number) {
      if (startRef.current === null) startRef.current = now;
      const elapsed = now - startRef.current;

      if (elapsed >= total) {
        setState({
          stepIndex: STORYBOARD.length - 1,
          stepProgress: 1,
          totalProgress: 1,
          done: true,
        });
        return; // stop the loop
      }

      // Find current beat.
      let idx = 0;
      for (let i = 0; i < STORYBOARD.length; i++) {
        if (elapsed >= offsets[i]) idx = i;
      }
      const within = (elapsed - offsets[idx]) / durations[idx];

      setState({
        stepIndex: idx,
        stepProgress: Math.min(1, Math.max(0, within)),
        totalProgress: elapsed / total,
        done: false,
      });

      rafRef.current = requestAnimationFrame(frame);
    }

    if (runningRef.current) {
      rafRef.current = requestAnimationFrame(frame);
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speed]);

  function restart() {
    startRef.current = null;
    runningRef.current = true;
    setState({ stepIndex: 0, stepProgress: 0, totalProgress: 0, done: false });
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(function loop(now) {
      if (startRef.current === null) startRef.current = now;
      const elapsed = now - startRef.current;
      if (elapsed >= total) {
        setState({ stepIndex: STORYBOARD.length - 1, stepProgress: 1, totalProgress: 1, done: true });
        return;
      }
      let idx = 0;
      for (let i = 0; i < STORYBOARD.length; i++) if (elapsed >= offsets[i]) idx = i;
      setState({
        stepIndex: idx,
        stepProgress: Math.min(1, (elapsed - offsets[idx]) / durations[idx]),
        totalProgress: elapsed / total,
        done: false,
      });
      rafRef.current = requestAnimationFrame(loop);
    });
  }

  return { ...state, restart };
}
