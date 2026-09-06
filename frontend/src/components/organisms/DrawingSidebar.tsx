import { ScrollArea } from "@radix-ui/react-scroll-area";
import { ChevronLeft, ChevronRight, Loader2, PanelLeft } from "lucide-react";

import { DrawingListItem } from "@/components/molecules/DrawingListItem";
import { UploadButton } from "@/components/molecules/UploadButton";
import type { DrawingSummary } from "@/api/types";

export interface UploadEntry {
  key: string;        // upl-<hex>
  fileName: string;
}

interface Props {
  drawings: DrawingSummary[];
  uploads: UploadEntry[];
  loading: boolean;
  selectedKey: string | null;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  onSelect: (key: string) => void;
  onUploaded: (drawingId: string, fileName: string) => void;
  uploadDisabled?: boolean;
}

const HERO_LABEL = "Hero (cached replay)";
const PRESTAGED_LABEL = "Pre-staged (live, cached after first run)";
const REAL_LABEL = "Real industry samples (live, no metric)";
const UPLOAD_LABEL = "Your uploads (live, one-shot)";

export function DrawingSidebar({
  drawings, uploads, loading, selectedKey,
  collapsed = false, onToggleCollapsed,
  onSelect, onUploaded, uploadDisabled,
}: Props) {
  const heroes = drawings.filter((d) => d.kind === "hero");
  const prestaged = drawings.filter((d) => d.kind === "prestaged");
  const real = drawings.filter((d) => d.kind === "real");

  if (collapsed) {
    return (
      <aside
        aria-label="P&ID drawings (collapsed)"
        className="flex h-full w-12 shrink-0 flex-col items-center gap-2 border-r border-border-default bg-surface py-3"
      >
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label="Show drawings sidebar"
          title="도면 사이드바 펼치기"
          className="rounded-md border border-border-default bg-surface p-2 text-fg-secondary transition hover:border-accent hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          <ChevronRight aria-hidden size={16} />
        </button>
        <PanelLeft aria-hidden size={14} className="text-fg-muted" />
        <span
          className="rotate-180 text-[10px] font-semibold uppercase tracking-wider text-fg-muted"
          style={{ writingMode: "vertical-rl" }}
        >
          {loading ? "…" : `${drawings.length + uploads.length} drawings`}
        </span>
      </aside>
    );
  }

  return (
    <aside
      aria-label="P&ID drawings"
      className="flex h-full w-72 shrink-0 flex-col border-r border-border-default bg-surface"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-fg-muted">
          Drawings
        </h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-fg-muted" aria-live="polite">
            {loading ? "loading…" : `${drawings.length + uploads.length} total`}
          </span>
          {onToggleCollapsed ? (
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label="Hide drawings sidebar"
              title="도면 사이드바 숨기기"
              className="rounded p-1 text-fg-muted transition hover:bg-raised hover:text-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              <ChevronLeft aria-hidden size={14} />
            </button>
          ) : null}
        </div>
      </div>
      <ScrollArea className="flex-1 overflow-y-auto px-3 pb-3">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-fg-muted">
            <Loader2 aria-hidden className="animate-spin" size={18} />
            <span className="sr-only">Loading drawings</span>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {heroes.length > 0 ? (
              <Section label={HERO_LABEL}>
                {heroes.map((d) => (
                  <DrawingListItem
                    key={d.key} drawing={d}
                    selected={selectedKey === d.key}
                    onSelect={onSelect}
                  />
                ))}
              </Section>
            ) : null}
            {prestaged.length > 0 ? (
              <Section label={PRESTAGED_LABEL}>
                {prestaged.map((d) => (
                  <DrawingListItem
                    key={d.key} drawing={d}
                    selected={selectedKey === d.key}
                    onSelect={onSelect}
                  />
                ))}
              </Section>
            ) : null}
            {real.length > 0 ? (
              <Section label={REAL_LABEL}>
                {real.map((d) => (
                  <DrawingListItem
                    key={d.key} drawing={d}
                    selected={selectedKey === d.key}
                    onSelect={onSelect}
                  />
                ))}
              </Section>
            ) : null}
            <Section label={UPLOAD_LABEL}>
              {uploads.length === 0 ? (
                <p className="px-3 text-xs text-fg-muted">
                  No uploads yet — drop a PDF or image to extract live.
                </p>
              ) : (
                <ul className="flex flex-col gap-2" role="list">
                  {uploads.map((u) => (
                    <li key={u.key}>
                      <button
                        type="button"
                        aria-pressed={selectedKey === u.key}
                        aria-label={`Select uploaded drawing ${u.fileName}`}
                        onClick={() => onSelect(u.key)}
                        className={[
                          "w-full rounded-md border px-3 py-2 text-left text-xs",
                          selectedKey === u.key
                            ? "border-accent bg-[var(--accent-soft)]"
                            : "border-border-default bg-surface hover:bg-raised",
                        ].join(" ")}
                      >
                        <div className="font-mono text-sm font-semibold text-fg-primary">
                          {u.fileName}
                        </div>
                        <div className="text-[10px] uppercase tracking-wide text-fg-muted">
                          {u.key}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="px-1 pt-2">
                <UploadButton onUploaded={onUploaded} disabled={uploadDisabled} />
              </div>
            </Section>
          </div>
        )}
      </ScrollArea>
    </aside>
  );
}

function Section({
  label, children,
}: { label: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">
        {label}
      </div>
      <div className="flex flex-col gap-2">
        {children}
      </div>
    </section>
  );
}
