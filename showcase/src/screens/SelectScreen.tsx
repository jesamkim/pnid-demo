import { motion } from "framer-motion";
import { ArrowLeft, ChevronRight, Loader2 } from "lucide-react";
import type { ShowcaseManifest } from "../lib/types";
import { conventionFor, imageUrl, titleFor } from "../lib/data";

interface Props {
  manifest: ShowcaseManifest | null;
  loading: boolean;
  onPick: (key: string) => void;
  onBack: () => void;
}

/**
 * SELECT — two large touch cards. Big hit areas (whole card), ripple via
 * whileTap, and a clear convention badge so the audience sees "two
 * different standards" at a glance.
 */
export function SelectScreen({ manifest, loading, onPick, onBack }: Props) {
  const drawings = manifest?.drawings ?? [];

  return (
    <motion.div
      className="absolute inset-0 flex flex-col px-12 py-10"
      initial={{ opacity: 0, scale: 1.03 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.45 }}
    >
      <div className="mb-8 flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-2 rounded-full border border-border-default px-4 py-2 text-fg-secondary"
        >
          <ArrowLeft size={18} /> 처음으로
        </button>
        <h2 className="text-2xl font-semibold">
          분석할 도면을 <span className="text-accent">선택</span>하세요
        </h2>
        <div className="w-28" />
      </div>

      <div className="grid flex-1 grid-cols-2 gap-8">
        {drawings.map((d, i) => {
          const t = titleFor(d.key);
          const conv = conventionFor(d.key);
          return (
            <motion.button
              key={d.key}
              disabled={loading}
              onClick={() => onPick(d.key)}
              className="group relative flex flex-col overflow-hidden rounded-3xl border border-border-strong bg-surface text-left shadow-elevation"
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 + i * 0.12, type: "spring", stiffness: 180 }}
              whileTap={{ scale: 0.97 }}
            >
              {/* Drawing preview */}
              <div className="relative flex-1 overflow-hidden bg-black/40">
                <img
                  src={imageUrl(d.image)}
                  alt={t.ko}
                  className="h-full w-full object-cover opacity-90 transition-transform duration-700 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-surface via-transparent to-transparent" />
                <span
                  className="absolute left-5 top-5 rounded-full px-3 py-1.5 text-sm font-semibold backdrop-blur"
                  style={{
                    background:
                      conv === "DIN EN 10628"
                        ? "color-mix(in srgb, #a78bfa 25%, transparent)"
                        : "color-mix(in srgb, var(--accent) 22%, transparent)",
                    color: conv === "DIN EN 10628" ? "#c4b5fd" : "var(--accent)",
                  }}
                >
                  {conv}
                </span>
              </div>

              {/* Caption */}
              <div className="flex items-center justify-between px-7 py-6">
                <div>
                  <div className="text-2xl font-bold">{t.ko}</div>
                  <div className="mt-1 text-sm text-fg-muted">{t.sub}</div>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-accent-fg transition-transform group-hover:translate-x-1">
                  <ChevronRight size={24} />
                </div>
              </div>
            </motion.button>
          );
        })}
      </div>

      {loading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-canvas/70 backdrop-blur">
          <div className="flex items-center gap-3 text-accent">
            <Loader2 className="animate-spin" size={28} />
            <span className="text-lg">분석 데이터 불러오는 중…</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}
