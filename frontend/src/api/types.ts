/**
 * TypeScript mirrors of the FastAPI response shapes in backend/api/main.py.
 *
 * We keep these manual (rather than generating from OpenAPI) because the
 * surface is small and pinning the contract here makes UI breakage from
 * backend renames immediately visible at compile time.
 */

export interface Health {
  status: "ok";
  drawings: string[];
  memory_backend: "agentcore" | "in-memory";
}

export type DrawingKind = "hero" | "prestaged" | "real" | "upload";

export interface DrawingSummary {
  key: string;
  pdf: string;
  title?: string;
  kind?: DrawingKind;
  has_cache?: boolean;
  has_ground_truth?: boolean;
  source?: string | null;          // license / publication note for real samples
  verdict: "pass" | "needs_correction" | string | null;
  iterations_used: number;
  counts: {
    equipment: number;
    instruments: number;
    lines: number;
    anomalies: number;
  };
}

export interface UploadResponse {
  drawing_id: string;
  ext: string;
  expires_at: number;
}

export interface DrawingsResponse {
  drawings: DrawingSummary[];
}

export interface Equipment {
  tag: string;
  type: string;
  service?: string | null;
  bbox?: [number, number, number, number] | null;
  page?: number;
  properties?: Record<string, string>;
}

export interface Instrument {
  tag: string;
  function?: string;
  loop_id?: string;
  located_on?: string | null;
  bbox?: [number, number, number, number] | null;
  page?: number;
}

export interface Line {
  line_no: string;
  size?: string | null;
  service?: string | null;
  spec?: string | null;
  from_tag?: string | null;
  to_tag?: string | null;
  geometry?: Array<[number, number]> | null;
  page?: number;
}

export interface Connection {
  from_tag: string;
  to_tag: string;
  via?: string | null;
  kind?: string | null;
}

export interface Anomaly {
  rule: string;
  severity: "high" | "medium" | "low" | string;
  violated_by: string;
  description: string;
  suggestion?: string | null;
}

export interface ProgressEvent {
  stage: string;
  detail: string;
  elapsed_s: number;
  extra?: Record<string, unknown>;
}

export interface PipelineDump {
  drawing_id: string;
  verdict: string;
  iterations_used: number;
  total_elapsed_s: number;
  extraction: {
    equipment: Equipment[];
    instruments: Instrument[];
    lines: Line[];
    connections: Connection[];
  };
  anomalies: Anomaly[];
  events: ProgressEvent[];
}

export interface SearchHit {
  drawing_id: string;
  kind: "equipment" | "instrument" | "line" | string;
  tag: string;
  score: number;
  text: string;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
}

export interface QuerySource {
  drawing_id: string;
  kind: string;
  tag: string;
  score: number;
}

export interface QueryResponse {
  query: string;
  answer: string;
  sources: QuerySource[];
}

export interface MemorySummary {
  verdict: string | null;
  iterations_used: number | null;
  total_elapsed_s: number | null;
  counts: {
    equipment: number;
    instruments: number;
    lines: number;
    connections: number;
  };
  anomaly_count: number;
}

export interface MemoryListEntry {
  drawing_id: string;
  saved_at_s: number;
  summary: MemorySummary;
}

export interface MemoryListResponse {
  actor_id: string;
  session_id: string;
  count: number;
  drawings: MemoryListEntry[];
}

export interface MemoryRecallResponse {
  actor_id: string;
  session_id: string;
  drawing_id: string;
  saved_at_s: number;
  summary: MemorySummary;
  payload: PipelineDump;
}

/* WebSocket frames pushed by /api/ws/extract/{key} */
export type WsFrame =
  | ({ type: "progress" } & ProgressEvent)
  | ({ type: "result" } & PipelineDump)
  | { type: "error"; message: string };

/* Geometry overlay (ground-truth bboxes for the canvas highlight layer). */
export type BBox = [number, number, number, number];

export interface GeometryEquipment {
  tag: string;
  type: string | null;
  service: string | null;
  bbox: BBox;
}

export interface GeometryInstrument {
  tag: string;
  function: string | null;
  located_on: string | null;
  bbox: BBox;
}

export interface GeometryLine {
  line_no: string;
  size: string | null;
  service: string | null;
  spec: string | null;
  from_tag: string | null;
  to_tag: string | null;
  geometry: Array<[number, number]> | null;
}

export interface GeometryResponse {
  drawing_id: string;
  source: "ground_truth";
  canvas: { width: number; height: number };
  equipment: GeometryEquipment[];
  instruments: GeometryInstrument[];
  lines: GeometryLine[];
}
