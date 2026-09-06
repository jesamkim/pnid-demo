import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ChevronRight, Database, MessageSquare, RotateCcw, Sparkles } from "lucide-react";
import type { ExtractionRecord, ScriptedQA } from "../lib/types";
import { Markdown } from "./Markdown";
import { VectorPanel } from "./VectorPanel";
import { BarChart } from "./BarChart";
import { PieChart } from "./PieChart";
import { chartForQuestion } from "../lib/chartFromQA";

interface Props {
  open: boolean;
  qa: ScriptedQA[];
  summary: string;
  extraction: ExtractionRecord;
  onClose: () => void;
  onRestart: () => void;
}

type Tab = "chat" | "vector";

/** Typewriter — reveals `text` char-by-char once `run` is true. */
function useTypewriter(text: string, run: boolean, cps = 45): string {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (!run) {
      setOut("");
      return;
    }
    let i = 0;
    const step = Math.max(1, Math.round(text.length / (text.length / cps) / 10));
    const id = window.setInterval(() => {
      i = Math.min(text.length, i + step);
      setOut(text.slice(0, i));
      if (i >= text.length) window.clearInterval(id);
    }, 1000 / cps);
    return () => window.clearInterval(id);
  }, [text, run, cps]);
  return out;
}

/**
 * HOOK CHATBOT — slides in after the analysis finishes. Scripted Q&A
 * only: tapping a chip plays a pre-frozen answer with a typewriter
 * effect. Ends with a CTA pointing to the full interactive demo running
 * on the adjacent device.
 */
export function HookChatbot({ open, qa, summary, extraction, onRestart }: Props) {
  const [tab, setTab] = useState<Tab>("chat");
  const [picked, setPicked] = useState<number | null>(null);
  // Collapsed = panel slid off-screen, leaving only a small edge tab so
  // the analysed drawing is fully visible. Auto-expanded each time the
  // panel (re)opens after a Run.
  const [collapsed, setCollapsed] = useState(false);
  const answer = picked !== null ? qa[picked]?.answer ?? "" : "";
  const typed = useTypewriter(answer, picked !== null && tab === "chat" && !collapsed, 55);

  // Reset state whenever the panel re-opens.
  useEffect(() => {
    if (open) {
      setPicked(null);
      setTab("chat");
      setCollapsed(false);
    }
  }, [open]);

  return (
    <AnimatePresence>
      {open && collapsed && (
        // Edge tab to re-open the panel — keeps the drawing unobstructed.
        <motion.button
          key="chat-reopen"
          onClick={() => setCollapsed(false)}
          className="absolute right-0 top-1/2 z-30 flex -translate-y-1/2 items-center gap-2 rounded-l-xl border border-r-0 border-border-strong bg-surface/95 py-4 pl-4 pr-3 text-sm font-semibold text-accent shadow-glow backdrop-blur-xl"
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 260, damping: 30 }}
        >
          <MessageSquare size={18} />
          <span className="[writing-mode:vertical-rl]">AI 질의 / 벡터</span>
        </motion.button>
      )}
      {open && !collapsed && (
        <motion.div
          className="absolute inset-y-0 right-0 z-30 flex w-[42%] min-w-[440px] flex-col border-l border-border-strong bg-surface/95 backdrop-blur-xl"
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 260, damping: 30 }}
        >
          {/* Tab switch + collapse */}
          <div className="flex items-center gap-2 border-b border-border-default px-5 pt-4">
            <button
              onClick={() => setTab("chat")}
              className="flex items-center gap-2 rounded-t-xl px-4 py-3 text-sm font-semibold transition-colors"
              style={{
                color: tab === "chat" ? "var(--accent)" : "var(--fg-muted)",
                borderBottom: `2px solid ${tab === "chat" ? "var(--accent)" : "transparent"}`,
              }}
            >
              <MessageSquare size={16} /> AI 질의
            </button>
            <button
              onClick={() => setTab("vector")}
              className="flex items-center gap-2 rounded-t-xl px-4 py-3 text-sm font-semibold transition-colors"
              style={{
                color: tab === "vector" ? "var(--accent)" : "var(--fg-muted)",
                borderBottom: `2px solid ${tab === "vector" ? "var(--accent)" : "transparent"}`,
              }}
            >
              <Database size={16} /> 벡터 인덱스
            </button>
            <button
              onClick={() => setCollapsed(true)}
              aria-label="패널 접기"
              title="접기 — 도면 전체 보기"
              className="ml-auto mb-1 flex h-9 w-9 items-center justify-center rounded-lg border border-border-default text-fg-muted transition-colors hover:border-accent hover:text-accent"
            >
              <ChevronRight size={18} />
            </button>
          </div>

          {tab === "vector" ? (
            <VectorPanel extraction={extraction} />
          ) : (
          <>
          {/* Summary card */}
          <div className="border-b border-border-default px-7 py-5">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-accent">
              <Sparkles size={15} /> 분석 요약
            </div>
            <p className="text-sm leading-relaxed text-fg-secondary line-clamp-4">
              {summary}
            </p>
          </div>

          {/* Conversation area */}
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-7 py-6">
            {picked !== null && (
              <>
                <div className="self-end rounded-2xl rounded-br-sm bg-accent px-5 py-3 text-accent-fg">
                  {qa[picked].question}
                </div>
                <motion.div
                  className="self-start rounded-2xl rounded-bl-sm border border-border-default bg-raised px-5 py-4"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  {/* While typing show raw text (tables would break mid-stream);
                      once complete, render the markdown + an optional chart. */}
                  {typed.length >= answer.length ? (
                    <>
                      {(() => {
                        const spec = chartForQuestion(qa[picked].question, extraction);
                        if (!spec) return null;
                        return spec.kind === "pie" ? (
                          <PieChart title={spec.title} slices={spec.bars} unit={spec.unit} />
                        ) : (
                          <BarChart title={spec.title} bars={spec.bars} unit={spec.unit} />
                        );
                      })()}
                      <Markdown text={answer} />
                    </>
                  ) : (
                    <p className="whitespace-pre-wrap text-fg-primary">{typed}</p>
                  )}
                  {qa[picked].sources.length > 0 && typed.length >= answer.length && (
                    <div className="mt-3 flex flex-wrap gap-2 border-t border-border-default pt-3">
                      {qa[picked].sources.map((s, i) => (
                        <span
                          key={i}
                          className="rounded-full bg-accent-soft px-2.5 py-1 font-mono text-xs text-accent"
                        >
                          {s.tag ?? s.kind}
                        </span>
                      ))}
                    </div>
                  )}
                </motion.div>
              </>
            )}

            {picked === null && (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-fg-muted">예시 질문을 눌러보세요</p>
                {qa.map((item, i) => (
                  <motion.button
                    key={i}
                    onClick={() => setPicked(i)}
                    className="flex items-center justify-between rounded-2xl border border-border-strong bg-raised px-5 py-4 text-left transition-colors hover:border-accent"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.15 + i * 0.1 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <span className="font-medium">{item.question}</span>
                    <ArrowRight size={18} className="text-accent" />
                  </motion.button>
                ))}
              </div>
            )}
          </div>
          </>
          )}

          {/* Footer actions */}
          <div className="border-t border-border-default px-7 py-5">
            <div className="flex gap-3">
              {tab === "chat" && picked !== null && (
                <button
                  onClick={() => setPicked(null)}
                  className="flex-1 rounded-xl border border-border-strong py-3 text-fg-secondary"
                >
                  다른 질문
                </button>
              )}
              <button
                onClick={onRestart}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-surface py-3 font-semibold text-fg-primary"
              >
                <RotateCcw size={18} /> 처음으로
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
