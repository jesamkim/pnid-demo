/**
 * Synthesize a GeometryResponse from a live extraction stream.
 *
 * Uploaded PDFs (`upl-*`) and real-industry samples (`real-*`) have no
 * ground-truth geometry on disk, so the static `/api/drawings/{key}/
 * geometry` endpoint returns 404 for them. To still light up the
 * traveling-light + bbox overlay during a live run, we shape the
 * Vision/Fusion agent's bbox + line-geometry output into the same
 * GeometryResponse contract that the synthetic drawings use.
 *
 * Inputs:
 *   - `result`: PipelineDump (from stream.result)
 *   - `events`: ProgressEvent[] — used to recover canvas dimensions
 *               (the orchestrator emits them in the `render` event's
 *               `extra: {canvas_width, canvas_height}`)
 *
 * Returns null when the stream hasn't yielded enough data yet.
 */
import type {
  GeometryResponse,
  GeometryEquipment,
  GeometryInstrument,
  GeometryLine,
  PipelineDump,
  ProgressEvent,
} from "@/api/types";

export function liveGeometryFrom(
  result: PipelineDump | null,
  events: ProgressEvent[],
): GeometryResponse | null {
  if (!result) return null;
  const canvas = canvasFromRenderEvent(events);
  if (!canvas) return null;

  const equipment: GeometryEquipment[] = result.extraction.equipment
    .filter((e) => Array.isArray(e.bbox) && e.bbox.length === 4)
    .map((e) => ({
      tag: e.tag,
      type: e.type ?? null,
      service: e.service ?? null,
      bbox: e.bbox as [number, number, number, number],
    }));

  const instruments: GeometryInstrument[] = result.extraction.instruments
    .filter((i) => Array.isArray(i.bbox) && i.bbox.length === 4)
    .map((i) => ({
      tag: i.tag,
      function: i.function ?? null,
      located_on: i.located_on ?? null,
      bbox: i.bbox as [number, number, number, number],
    }));

  const lines: GeometryLine[] = result.extraction.lines.map((l) => ({
    line_no: l.line_no,
    size: l.size ?? null,
    service: l.service ?? null,
    spec: l.spec ?? null,
    from_tag: l.from_tag ?? null,
    to_tag: l.to_tag ?? null,
    geometry: Array.isArray(l.geometry) && l.geometry.length > 0
      ? (l.geometry as Array<[number, number]>)
      : null,
  }));

  return {
    drawing_id: result.drawing_id,
    source: "ground_truth", // contract type — overlay treats it the same
    canvas,
    equipment,
    instruments,
    lines,
  };
}

function canvasFromRenderEvent(
  events: ProgressEvent[],
): { width: number; height: number } | null {
  // Find the most recent render event with canvas info in `extra`.
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev?.stage !== "render") continue;
    const w = ev.extra?.["canvas_width"];
    const h = ev.extra?.["canvas_height"];
    if (typeof w === "number" && typeof h === "number" && w > 0 && h > 0) {
      return { width: w, height: h };
    }
  }
  return null;
}
