/**
 * Thin fetch wrapper for the FastAPI backend.
 *
 * `API_BASE` defaults to "" so requests hit the Vite dev proxy in development
 * and the same origin in production (CloudFront → ALB → ECS).
 */
import type {
  DrawingsResponse,
  GeometryResponse,
  Health,
  MemoryListResponse,
  MemoryRecallResponse,
  PipelineDump,
  QueryResponse,
  SearchResponse,
  UploadResponse,
  WsFrame,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function jsonGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { signal });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function jsonPost<T, B>(path: string, body: B, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export const api = {
  health: (signal?: AbortSignal) => jsonGet<Health>("/api/health", signal),
  drawings: (signal?: AbortSignal) =>
    jsonGet<DrawingsResponse>("/api/drawings", signal),
  pipeline: (key: string, signal?: AbortSignal) =>
    jsonGet<PipelineDump>(`/api/drawings/${key}/pipeline`, signal),
  geometry: (key: string, signal?: AbortSignal) =>
    jsonGet<GeometryResponse>(`/api/drawings/${key}/geometry`, signal),
  imageUrl: (key: string, dpi = 150) =>
    `${API_BASE}/api/drawings/${key}/image?dpi=${dpi}`,
  search: (
    body: { query: string; top_k?: number; kind_filter?: string | null; drawing_filter?: string | null },
    signal?: AbortSignal,
  ) => jsonPost<SearchResponse, typeof body>("/api/search", body, signal),
  query: (
    body: { query: string; top_k?: number; drawing_filter?: string | null },
    signal?: AbortSignal,
  ) => jsonPost<QueryResponse, typeof body>("/api/query", body, signal),
  indexRun: (
    body: { drawing_id: string; extraction: PipelineDump["extraction"] },
    signal?: AbortSignal,
  ) => jsonPost<{ drawing_id: string; indexed_docs: number }, typeof body>(
    "/api/index_run", body, signal,
  ),
  summary: (
    body: {
      drawing_id: string;
      title?: string | null;
      extraction: PipelineDump["extraction"];
      verdict: string;
      iterations_used?: number;
      anomalies?: Array<Record<string, unknown>>;
    },
    signal?: AbortSignal,
  ) =>
    jsonPost<{
      drawing_id: string;
      summary: string;
      suggested_queries: Array<{ label: string; text: string }>;
      storage: { search_index: string; memory_backend: string };
    }, typeof body>("/api/summary", body, signal),
  uploadDrawing: async (file: File): Promise<UploadResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/api/uploads`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) throw new Error(`POST /api/uploads -> ${res.status}`);
    return (await res.json()) as UploadResponse;
  },
  memoryList: (sessionId: string, actorId?: string, signal?: AbortSignal) => {
    const qs = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
    return jsonGet<MemoryListResponse>(
      `/api/memory/${encodeURIComponent(sessionId)}${qs}`,
      signal,
    );
  },
  memoryRecall: (
    sessionId: string,
    drawing: string,
    actorId?: string,
    signal?: AbortSignal,
  ) => {
    const qs = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
    return jsonGet<MemoryRecallResponse>(
      `/api/memory/${encodeURIComponent(sessionId)}/${encodeURIComponent(drawing)}${qs}`,
      signal,
    );
  },
};

/**
 * Open the live extraction WebSocket. Caller wires the four event handlers
 * and gets back a function to close the connection.
 */
export interface WsHandlers {
  onProgress?: (frame: WsFrame & { type: "progress" }) => void;
  onResult?: (frame: WsFrame & { type: "result" }) => void;
  onError?: (frame: WsFrame & { type: "error" }) => void;
  onClose?: () => void;
  /** Transport-level errors: socket `error` events and malformed frames
   * that can't be JSON-parsed. Lets the UI surface a real diagnostic
   * instead of only a generic "stream closed" later. */
  onSocketError?: (message: string) => void;
}

export function openExtractStream(
  key: string,
  opts: { sessionId?: string; actorId?: string } = {},
  handlers: WsHandlers = {},
): () => void {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = API_BASE
    ? new URL(API_BASE, window.location.origin).host
    : window.location.host;
  const params = new URLSearchParams();
  if (opts.sessionId) params.set("session_id", opts.sessionId);
  if (opts.actorId) params.set("actor_id", opts.actorId);
  const qs = params.toString() ? `?${params}` : "";
  const ws = new WebSocket(`${proto}//${host}/api/ws/extract/${encodeURIComponent(key)}${qs}`);

  ws.addEventListener("message", (event) => {
    let frame: WsFrame;
    try {
      frame = JSON.parse(event.data) as WsFrame;
    } catch {
      handlers.onSocketError?.("received a malformed stream frame");
      return;
    }
    if (frame.type === "progress") handlers.onProgress?.(frame);
    else if (frame.type === "result") handlers.onResult?.(frame);
    else if (frame.type === "error") handlers.onError?.(frame);
  });
  ws.addEventListener("error", () => handlers.onSocketError?.("stream connection error"));
  ws.addEventListener("close", () => handlers.onClose?.());

  return () => {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  };
}
