/**
 * Static data loader. All showcase content lives under `public/data/`
 * and is fetched once at startup — no backend, no live inference.
 */
import type { Convention, ShowcaseDrawing, ShowcaseManifest } from "./types";

// Vite serves `public/` at the app root; `base: "./"` keeps this relative
// so it works under any CloudFront path.
const DATA_BASE = "data";

export async function loadManifest(): Promise<ShowcaseManifest> {
  const res = await fetch(`${DATA_BASE}/manifest.json`);
  if (!res.ok) throw new Error(`manifest load failed: ${res.status}`);
  return res.json();
}

export async function loadDrawing(key: string): Promise<ShowcaseDrawing> {
  const res = await fetch(`${DATA_BASE}/${key}.json`);
  if (!res.ok) throw new Error(`drawing ${key} load failed: ${res.status}`);
  return res.json();
}

export function imageUrl(rel: string): string {
  return `${DATA_BASE}/${rel}`;
}

/** Decide the convention badge from the drawing key. DIN drawings carry
 * "din" (or the legacy "uer" real sample) in their key; everything else
 * is ISA-5.1. */
export function conventionFor(key: string): Convention {
  return /din|uer/.test(key) ? "DIN EN 10628" : "ISA-5.1";
}

/** A short human title per drawing for the select grid. */
export function titleFor(key: string): { ko: string; sub: string } {
  if (/din|uer/.test(key)) {
    return { ko: "냉각·진공 설비 공정도 (독일 표준)", sub: "DIN EN 10628 · 합성 도면" };
  }
  return { ko: "복합 정유 공정도 (ISA 표준)", sub: "ISA-5.1 · 대형 P&ID" };
}
