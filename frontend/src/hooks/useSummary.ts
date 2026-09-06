/**
 * useSummary — fires once per finished extraction to fetch the Korean
 * NL summary + storage notice from `/api/summary`.
 *
 * Triggers when:
 *   - liveDone (stream.status === "done") flips true, OR
 *   - replayDone (replay.status === "done") flips true
 * Resets on drawing change.
 *
 * Idempotent: re-renders without state change don't re-fetch.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/api/client";
import type { PipelineDump } from "@/api/types";

export interface SummaryState {
  status: "idle" | "loading" | "ready" | "error";
  text: string;
  suggestedQueries: ReadonlyArray<{ label: string; text: string }>;
  storage: { search_index: string; memory_backend: string } | null;
  error: string | null;
}

const initial: SummaryState = {
  status: "idle",
  text: "",
  suggestedQueries: [],
  storage: null,
  error: null,
};

export function useSummary(drawingKey: string | null) {
  const [state, setState] = useState<SummaryState>(initial);
  const lastKeyRef = useRef<string | null>(null);
  // Monotonic generation token. Every generate() call (and every drawing
  // change / unmount) bumps it; in-flight work checks the token before
  // calling setState so a stale summary can't land on a newer drawing.
  const genRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const clearRetry = () => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  };

  // Reset whenever the drawing changes — even if the same Run finishes
  // twice we re-summarize because the user explicitly asked for it.
  useEffect(() => {
    if (lastKeyRef.current !== drawingKey) {
      lastKeyRef.current = drawingKey;
      genRef.current++; // invalidate any in-flight generate()
      clearRetry();
      setState(initial);
    }
  }, [drawingKey]);

  // Track mount so async work never setStates after unmount.
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current++;
      clearRetry();
    };
  }, []);

  const generate = useCallback(
    async (
      result: PipelineDump,
      title?: string | null,
    ) => {
      const myGen = ++genRef.current;
      clearRetry();
      const alive = () => mountedRef.current && genRef.current === myGen;
      setState({ status: "loading", text: "", suggestedQueries: [], storage: null, error: null });
      const body = {
        drawing_id: result.drawing_id,
        title: title ?? null,
        extraction: result.extraction,
        verdict: result.verdict,
        iterations_used: result.iterations_used,
        anomalies: (result.anomalies ?? []) as unknown as Array<Record<string, unknown>>,
      };
      // Retry on transient errors. Two failure shapes worth retrying:
      //   1. Gateway 5xx (50[234]) — CloudFront gave up before the
      //      backend finished. Backend kept working, so a follow-up
      //      typically hits the warmed Strands agent quickly.
      //   2. Network abort — Safari/Chrome surface this as
      //      "Load failed" / "Failed to fetch" / "NetworkError"
      //      (TypeError DOMException). Happens when the connection
      //      is closed mid-flight, e.g. during an ECS rolling
      //      redeploy or a CloudFront edge swap.
      const isTransient = (msg: string) =>
        /\b(50[234])\b/.test(msg) ||
        /load failed/i.test(msg) ||
        /failed to fetch/i.test(msg) ||
        /networkerror/i.test(msg) ||
        /aborted/i.test(msg);
      const MAX_ATTEMPTS = 3;
      let lastErr: unknown = null;
      for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
        try {
          const res = await api.summary(body);
          if (!alive()) return; // drawing changed / unmounted mid-flight
          setState({
            status: "ready",
            text: res.summary,
            suggestedQueries: res.suggested_queries ?? [],
            storage: res.storage,
            error: null,
          });
          return;
        } catch (e: unknown) {
          if (!alive()) return;
          lastErr = e;
          const msg = e instanceof Error ? e.message : String(e);
          if (attempt < MAX_ATTEMPTS - 1 && isTransient(msg)) {
            // Linear back-off: 1.5s, 3s — short enough that the user
            // doesn't notice on the happy path, long enough that the
            // backend has time to finish a long Sonnet completion.
            // Cancellable: a drawing switch clears retryTimerRef.
            const waited = await new Promise<boolean>((resolve) => {
              retryTimerRef.current = setTimeout(() => resolve(true), 1500 * (attempt + 1));
            });
            if (!waited || !alive()) return;
            continue;
          }
          break;
        }
      }
      if (!alive()) return;
      setState({
        status: "error",
        text: "",
        suggestedQueries: [],
        storage: null,
        error: lastErr instanceof Error ? lastErr.message : String(lastErr),
      });
    },
    [],
  );

  const reset = useCallback(() => {
    genRef.current++;
    clearRetry();
    setState(initial);
  }, []);

  return { ...state, generate, reset };
}
