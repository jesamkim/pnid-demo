/**
 * SummaryCard — Korean NL summary + Vector Store storage notice.
 *
 * Renders only after a Run finishes (liveDone or replayDone). Three
 * states: loading, ready, error. The storage row has icons for the
 * SearchIndex (BM25 + Cohere Embed v4) and AgentCore Memory destinations
 * so the audience visibly sees that the result was persisted.
 */
import { motion } from "framer-motion";
import { CheckCircle2, Database, Loader2, Sparkles } from "lucide-react";

import { MarkdownLite } from "@/lib/markdown";
import type { SummaryState } from "@/hooks/useSummary";

interface Props {
  state: SummaryState;
}

export function SummaryCard({ state }: Props) {
  if (state.status === "idle") return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      aria-label="분석 요약"
      className="rounded-lg border border-accent/40 bg-[var(--bg-surface)]/95 p-4 shadow-[var(--shadow-glow)] ring-1 ring-[var(--accent-soft)]"
    >
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent">
        <Sparkles aria-hidden size={14} />
        분석 요약 (Sonnet 4.6)
      </div>
      {state.status === "loading" ? (
        <div className="flex items-center gap-2 text-sm text-fg-muted">
          <Loader2 aria-hidden className="animate-spin" size={16} />
          한국어 요약 생성 중...
        </div>
      ) : state.status === "error" ? (
        <p className="text-sm text-danger" aria-live="polite">
          요약 생성 실패: {state.error}
        </p>
      ) : (
        <>
          <div className="text-sm leading-relaxed text-fg-primary">
            <MarkdownLite text={state.text} />
          </div>
          {state.storage ? (
            <ul className="mt-3 grid grid-cols-1 gap-1 border-t border-border-default pt-3 text-xs text-fg-secondary sm:grid-cols-2">
              <li className="flex items-center gap-2">
                <CheckCircle2 aria-hidden size={13} className="text-success" />
                <span>SearchIndex 인덱싱 완료</span>
                <span className="ml-auto font-mono text-[10px] text-fg-muted">
                  {state.storage.search_index}
                </span>
              </li>
              <li className="flex items-center gap-2">
                <Database aria-hidden size={13} className="text-accent" />
                <span>AgentCore Memory 저장 완료</span>
                <span className="ml-auto font-mono text-[10px] text-fg-muted">
                  {state.storage.memory_backend}
                </span>
              </li>
            </ul>
          ) : null}
        </>
      )}
    </motion.section>
  );
}
