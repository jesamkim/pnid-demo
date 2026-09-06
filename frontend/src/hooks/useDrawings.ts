import { useEffect, useState } from "react";

import { api } from "@/api/client";
import type {
  DrawingSummary,
  GeometryResponse,
  Health,
  PipelineDump,
} from "@/api/types";

export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    api.health(ctrl.signal).then(setHealth).catch(() => setHealth(null));
    return () => ctrl.abort();
  }, []);
  return health;
}

export function useDrawingList() {
  const [drawings, setDrawings] = useState<DrawingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api
      .drawings(ctrl.signal)
      .then((r) => setDrawings(r.drawings))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, []);

  return { drawings, loading, error };
}

export function usePipeline(key: string | null) {
  const [pipeline, setPipeline] = useState<PipelineDump | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Always clear stale pipeline immediately — without this the previous
    // drawing's events stay live for the few hundred ms it takes the new
    // fetch to come back, which lets stale-cursor reads slip through into
    // child components that assume `pipeline` matches `key`.
    setPipeline(null);
    if (!key) return;
    setLoading(true);
    setError(null);
    const ctrl = new AbortController();
    api
      .pipeline(key, ctrl.signal)
      .then(setPipeline)
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [key]);

  return { pipeline, loading, error };
}

export function useGeometry(key: string | null) {
  const [geometry, setGeometry] = useState<GeometryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setGeometry(null);
    setError(null);
    if (!key) return;
    setLoading(true);
    const ctrl = new AbortController();
    api
      .geometry(key, ctrl.signal)
      .then(setGeometry)
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setGeometry(null);
        // A 404 just means "no GT geometry for this drawing" (uploads /
        // real samples synthesize it from the live stream instead), so
        // don't surface that as an error; flag only unexpected failures.
        const msg = e instanceof Error ? e.message : String(e);
        if (!/\b404\b/.test(msg)) setError(msg);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [key]);

  return { geometry, loading, error };
}
