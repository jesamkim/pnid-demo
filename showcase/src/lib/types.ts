/**
 * Static showcase data contract — mirrors the JSON emitted by
 * `scripts/freeze_showcase.py`. The showcase NEVER calls a backend; it
 * fetches these files from `public/data/` at runtime.
 */

// [x1, y1, x2, y2] in source-image pixel coords
export type BBox = [number, number, number, number];

export interface GeometryEquipment {
  tag: string;
  type: string | null;
  service?: string | null;
  bbox: BBox | null;
}

export interface GeometryInstrument {
  tag: string;
  function?: string | null;
  located_on?: string | null;
  bbox: BBox | null;
}

export interface GeometryLine {
  line_no: string | null;
  size?: string | null;
  service?: string | null;
  spec?: string | null;
  from_tag?: string | null;
  to_tag?: string | null;
  geometry: Array<[number, number]> | null;
}

export interface Geometry {
  equipment: GeometryEquipment[];
  instruments: GeometryInstrument[];
  lines: GeometryLine[];
}

/** One pipeline progress event captured at freeze time. */
export interface FrozenEvent {
  stage: string;
  detail: string;
  elapsed_s: number;
  extra?: Record<string, unknown>;
}

export interface ScriptedQA {
  question: string;
  answer: string;
  sources: Array<{ tag: string | null; kind: string; score: number }>;
}

export interface Metrics {
  equipment: number;
  instruments: number;
  lines: number;
  connections: number;
}

/** One extracted record as stored in the (demo) vector store. */
export interface ExtractionRecord {
  equipment: Array<{ tag: string; type?: string | null; service?: string | null }>;
  instruments: Array<{ tag: string; function?: string | null; located_on?: string | null }>;
  lines: Array<{ line_no: string | null; size?: string | null; service?: string | null; spec?: string | null }>;
  connections: Array<{ from_tag: string; to_tag: string; type?: string; via_line?: string | null }>;
}

/** Full frozen payload for one drawing (public/data/{key}.json). */
export interface ShowcaseDrawing {
  drawing_id: string;
  image: string; // relative path under public/data/, e.g. "images/00.png"
  canvas: { width: number; height: number };
  events: FrozenEvent[];
  extraction: ExtractionRecord;
  anomalies: unknown[];
  verdict: string | null;
  geometry: Geometry;
  summary: string;
  metrics: Metrics;
  qa: ScriptedQA[];
  frozen_at: string;
}

/** public/data/manifest.json */
export interface ShowcaseManifest {
  drawings: Array<{
    key: string;
    title: string;
    image: string;
    metrics: Metrics;
  }>;
}

/** Convention label derived from the drawing key / events. */
export type Convention = "ISA-5.1" | "DIN EN 10628";
