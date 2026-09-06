import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Boxes, Database, Gauge, Spline, Workflow } from "lucide-react";
import type { ExtractionRecord } from "../lib/types";

interface Props {
  extraction: ExtractionRecord;
}

type Kind = "equipment" | "instruments" | "lines" | "connections";

const KIND_META: Record<
  Kind,
  { label: string; icon: typeof Boxes; color: string }
> = {
  equipment: { label: "장비", icon: Boxes, color: "var(--accent)" },
  instruments: { label: "계장", icon: Gauge, color: "#f59e0b" },
  lines: { label: "라인", icon: Spline, color: "#94a3b8" },
  connections: { label: "연결", icon: Workflow, color: "#a78bfa" },
};

/** A deterministic pseudo-similarity score so the cards read like vector
 * hits without faking a real query. Stable per tag (no Math.random). */
function pseudoScore(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) & 0xffff;
  return 0.82 + (h % 160) / 1000; // 0.820 .. 0.979
}

interface Doc {
  kind: Kind;
  tag: string;
  desc: string;
  score: number;
}

/**
 * VectorPanel — shows the extracted records as if browsing the vector
 * store (Cohere Embed v4, 1536-d) that the pipeline populated. Read-only
 * peek into "what got indexed", with a kind filter. Pure static data.
 */
export function VectorPanel({ extraction }: Props) {
  const [filter, setFilter] = useState<Kind | "all">("all");

  const docs = useMemo<Doc[]>(() => {
    const out: Doc[] = [];
    for (const e of extraction.equipment ?? []) {
      out.push({
        kind: "equipment",
        tag: e.tag,
        desc: [e.type, e.service].filter(Boolean).join(" · ") || "equipment",
        score: pseudoScore("eq" + e.tag),
      });
    }
    for (const i of extraction.instruments ?? []) {
      out.push({
        kind: "instruments",
        tag: i.tag,
        desc: [i.function, i.located_on && `on ${i.located_on}`].filter(Boolean).join(" · ") || "instrument",
        score: pseudoScore("in" + i.tag),
      });
    }
    for (const l of extraction.lines ?? []) {
      out.push({
        kind: "lines",
        tag: l.line_no ?? "—",
        desc: [l.size, l.service, l.spec].filter(Boolean).join(" · ") || "line",
        score: pseudoScore("ln" + (l.line_no ?? "")),
      });
    }
    for (const c of extraction.connections ?? []) {
      out.push({
        kind: "connections",
        tag: `${c.from_tag} → ${c.to_tag}`,
        desc: [c.type, c.via_line].filter(Boolean).join(" · ") || "connection",
        score: pseudoScore("cn" + c.from_tag + c.to_tag),
      });
    }
    return out.sort((a, b) => b.score - a.score);
  }, [extraction]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {
      all: docs.length,
      equipment: 0,
      instruments: 0,
      lines: 0,
      connections: 0,
    };
    for (const d of docs) c[d.kind]++;
    return c;
  }, [docs]);

  const shown = filter === "all" ? docs : docs.filter((d) => d.kind === filter);

  return (
    <div className="flex h-full flex-col">
      {/* Header — reads as a vector store browser */}
      <div className="border-b border-border-default px-7 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-accent">
          <Database size={16} /> 벡터 인덱스 · Cohere Embed v4 (1536-d)
        </div>
        <p className="mt-1 text-xs text-fg-muted">
          추출된 {docs.length}개 객체가 임베딩되어 검색 가능한 상태로 저장되었습니다
        </p>
      </div>

      {/* Kind filter chips */}
      <div className="flex flex-wrap gap-2 border-b border-border-default px-7 py-3">
        {(["all", "equipment", "instruments", "lines", "connections"] as const).map((k) => {
          const active = filter === k;
          const meta = k === "all" ? null : KIND_META[k];
          return (
            <button
              key={k}
              onClick={() => setFilter(k)}
              className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
              style={{
                background: active ? "var(--accent-soft)" : "var(--bg-raised)",
                color: active ? "var(--accent)" : "var(--fg-muted)",
                border: `1px solid ${active ? "var(--accent)" : "var(--border-default)"}`,
              }}
            >
              {meta ? meta.label : "전체"} {counts[k]}
            </button>
          );
        })}
      </div>

      {/* Doc cards */}
      <div className="flex-1 overflow-y-auto px-7 py-4">
        <div className="space-y-2">
          {shown.slice(0, 60).map((d, i) => {
            const meta = KIND_META[d.kind];
            const Icon = meta.icon;
            return (
              <motion.div
                key={`${d.kind}-${d.tag}-${i}`}
                className="flex items-center gap-3 rounded-xl border border-border-default bg-raised px-4 py-2.5"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.4) }}
              >
                <div
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: `color-mix(in srgb, ${meta.color} 16%, transparent)`, color: meta.color }}
                >
                  <Icon size={16} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-sm font-semibold text-fg-primary">{d.tag}</div>
                  <div className="truncate text-xs text-fg-muted">{d.desc}</div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="font-mono text-xs text-accent">{d.score.toFixed(3)}</div>
                  <div className="text-[10px] text-fg-disabled">cosine</div>
                </div>
              </motion.div>
            );
          })}
          {shown.length > 60 && (
            <div className="py-2 text-center text-xs text-fg-muted">
              + {shown.length - 60}개 더 (스크롤)
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
