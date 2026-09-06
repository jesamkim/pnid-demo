/**
 * Geometry helpers for the P&ID overlay layer.
 *
 * Coordinates flow:
 *   1. Ground-truth `canvas` (px) — the synthetic SVG's natural size
 *      (e.g. 2700 x 1600). All bboxes are in this space.
 *   2. Display rect — the rendered <img> bounding rect inside our viewer.
 *   3. We render the SVG overlay at the display size and scale every
 *      coordinate by `scale = displayWidth / canvasWidth` (uniform; the
 *      backend image preserves aspect ratio).
 *
 * Helpers here are pure and side-effect-free so they can be unit-tested
 * in isolation if needed.
 */
import type { BBox, GeometryEquipment, GeometryInstrument } from "@/api/types";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function bboxToRect(bbox: BBox): Rect {
  const [x1, y1, x2, y2] = bbox;
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  };
}

export function bboxCenter(bbox: BBox): { cx: number; cy: number } {
  const r = bboxToRect(bbox);
  return { cx: r.x + r.width / 2, cy: r.y + r.height / 2 };
}

export type TaggedItem = GeometryEquipment | GeometryInstrument;

export function buildTagIndex<T extends TaggedItem>(
  items: readonly T[],
): Map<string, T> {
  const m = new Map<string, T>();
  for (const item of items) m.set(item.tag, item);
  return m;
}

/**
 * Build a single SVG path string that connects two bbox centers with a
 * 90-degree elbow (orthogonal) — matches the look of the rest of the
 * P&ID where pipes run along the grid. Returns `null` when either tag
 * is missing geometry, so the caller can skip rendering that line.
 */
export function elbowPath(
  fromBbox: BBox | undefined,
  toBbox: BBox | undefined,
): string | null {
  if (!fromBbox || !toBbox) return null;
  const a = bboxCenter(fromBbox);
  const b = bboxCenter(toBbox);
  const midX = (a.cx + b.cx) / 2;
  return `M ${a.cx},${a.cy} L ${midX},${a.cy} L ${midX},${b.cy} L ${b.cx},${b.cy}`;
}

/**
 * Convert a polyline (`[[x,y],[x,y],...]`) into an SVG `d` attribute.
 * Returns null when the input is empty so the caller can skip rendering.
 */
export function polylinePath(
  geometry: ReadonlyArray<readonly [number, number]> | null | undefined,
): string | null {
  if (!geometry || geometry.length < 2) return null;
  return geometry
    .map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x},${y}`)
    .join(" ");
}

/**
 * Compute total length of a polyline given as a list of points.
 * Used to feed strokeDasharray for the traveling-light animation.
 */
export function polylineLength(points: Array<{ x: number; y: number }>): number {
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]!;
    const b = points[i]!;
    total += Math.hypot(b.x - a.x, b.y - a.y);
  }
  return total;
}

/**
 * Returns true if the user has indicated they prefer reduced motion.
 * Defaults to false in non-DOM environments.
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
