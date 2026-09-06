/**
 * useExtractStream — drives a live extraction over the
 * `/api/ws/extract/{key}` WebSocket and exposes the streaming state
 * to UI components.
 *
 * Lifecycle:
 *   idle → connecting → streaming → done | error
 *
 * Caller invokes `start(key)` to kick off; cleanup on unmount or when
 * `start` is invoked with a new key (the previous WebSocket is closed).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { openExtractStream } from "@/api/client";
import type { PipelineDump, ProgressEvent } from "@/api/types";

export type StreamStatus = "idle" | "connecting" | "streaming" | "done" | "error";

export interface ExtractStreamState {
  status: StreamStatus;
  drawingKey: string | null;
  events: ProgressEvent[];
  result: PipelineDump | null;
  error: string | null;
  /** Index of the most recent event, or null when nothing has streamed yet. */
  cursor: number | null;
}

const INITIAL: ExtractStreamState = {
  status: "idle",
  drawingKey: null,
  events: [],
  result: null,
  error: null,
  cursor: null,
};

export interface UseExtractStreamReturn extends ExtractStreamState {
  start: (key: string, opts?: { sessionId?: string; actorId?: string }) => void;
  cancel: () => void;
  reset: () => void;
}

export function useExtractStream(): UseExtractStreamReturn {
  const [state, setState] = useState<ExtractStreamState>(INITIAL);
  const closerRef = useRef<(() => void) | null>(null);
  // Marks closes we initiated (cancel / new start / unmount) so the
  // socket's onClose handler doesn't mis-report them as "stream closed
  // unexpectedly".
  const intentionalCloseRef = useRef(false);

  const cancel = useCallback(() => {
    intentionalCloseRef.current = true;
    closerRef.current?.();
    closerRef.current = null;
  }, []);

  const reset = useCallback(() => {
    cancel();
    setState(INITIAL);
  }, [cancel]);

  const start = useCallback(
    (key: string, opts: { sessionId?: string; actorId?: string } = {}) => {
      // Close any in-flight stream from a previous key.
      cancel();
      // This run's own close should NOT be treated as intentional —
      // only an explicit cancel()/unmount marks it so.
      intentionalCloseRef.current = false;
      setState({
        status: "connecting",
        drawingKey: key,
        events: [],
        result: null,
        error: null,
        cursor: null,
      });
      const close = openExtractStream(key, opts, {
        onProgress: (frame) => {
          setState((prev) => {
            if (prev.drawingKey !== key) return prev;
            const events = [...prev.events, frame];
            return {
              ...prev,
              status: "streaming",
              events,
              cursor: events.length - 1,
            };
          });
        },
        onResult: (frame) => {
          setState((prev) => {
            if (prev.drawingKey !== key) return prev;
            return {
              ...prev,
              status: "done",
              result: { ...frame },
              // Result frames carry the final list of events too — prefer
              // those if richer than what we already streamed.
              events:
                frame.events && frame.events.length >= prev.events.length
                  ? frame.events
                  : prev.events,
              cursor:
                frame.events && frame.events.length > 0
                  ? frame.events.length - 1
                  : prev.cursor,
            };
          });
        },
        onError: (frame) => {
          setState((prev) =>
            prev.drawingKey !== key
              ? prev
              : { ...prev, status: "error", error: frame.message },
          );
        },
        onSocketError: (message) => {
          if (intentionalCloseRef.current) return;
          setState((prev) => {
            if (prev.drawingKey !== key || prev.status === "done") return prev;
            return { ...prev, status: "error", error: message };
          });
        },
        onClose: () => {
          // A close we initiated (cancel / new start / unmount) is not an
          // error — settle to idle instead of flashing a live error.
          if (intentionalCloseRef.current) {
            intentionalCloseRef.current = false;
            setState((prev) =>
              prev.drawingKey === key && prev.status !== "done"
                ? INITIAL
                : prev,
            );
            return;
          }
          setState((prev) => {
            if (prev.drawingKey !== key) return prev;
            // If we never received a result frame, treat unexpected close as error.
            if (prev.status === "streaming" || prev.status === "connecting") {
              return { ...prev, status: "error", error: "stream closed unexpectedly" };
            }
            return prev;
          });
        },
      });
      closerRef.current = close;
    },
    [cancel],
  );

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      closerRef.current?.();
      closerRef.current = null;
    };
  }, []);

  return { ...state, start, cancel, reset };
}
