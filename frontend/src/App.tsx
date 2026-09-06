/**
 * App shell.
 *
 * Behaviour rules:
 *   - When neither Replay nor Live is running, the timeline and the
 *     anomaly panel are EMPTY. The cached pipeline is fetched in the
 *     background but only rendered once a Run is triggered. This
 *     matches the visual claim that nothing has been analysed yet.
 *   - Hero drawings (01, 01b) default-click → cached replay. Shift+click
 *     forces a real Bedrock run.
 *   - Pre-staged drawings (02..04) default-click → cached replay if a
 *     cache exists, else real run. Shift+click forces real run.
 *   - Uploaded drawings (`upl-*`) always run real Bedrock.
 *   - Step banner overlays the canvas for every Run, replay or live.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/api/client";
import { AgentTimeline } from "@/components/organisms/AgentTimeline";
import { AnomalyPanel } from "@/components/organisms/AnomalyPanel";
import { DrawingSidebar, type UploadEntry } from "@/components/organisms/DrawingSidebar";
import { Header } from "@/components/organisms/Header";
import { MetricCards } from "@/components/organisms/MetricCards";
import { PipelineStepper } from "@/components/organisms/PipelineStepper";
import { PnidViewer } from "@/components/organisms/PnidViewer";
import { QueryPanel } from "@/components/organisms/QueryPanel";
import { SummaryCard } from "@/components/organisms/SummaryCard";
import { buildAnomalyTags } from "@/components/organisms/PnidOverlay";
import {
  useDrawingList,
  useGeometry,
  useHealth,
  usePipeline,
} from "@/hooks/useDrawings";
import { useExtractStream } from "@/hooks/useExtractStream";
import { useSummary } from "@/hooks/useSummary";
import { liveGeometryFrom } from "@/lib/liveGeometry";
import {
  stagePhase,
  usePipelineReplay,
} from "@/hooks/usePipelineReplay";
import type { ReplayPhase } from "@/hooks/usePipelineReplay";

const DEMO_SESSION_ID = "demo-default";

function BottomTabs({
  timelineEvents, timelineLoading, timelineTotal, timelineIters,
  timelineVerdict, timelineCursor, anomalies, onSelectAnomalyTag,
}: {
  timelineEvents: any[];
  timelineLoading: boolean;
  timelineTotal: number | null;
  timelineIters: number | null;
  timelineVerdict: string | null;
  timelineCursor: number | null;
  anomalies: any[];
  onSelectAnomalyTag: (tag: string) => void;
}) {
  const [tab, setTab] = useState<"timeline" | "anomalies">("timeline");
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex gap-1 border-b border-border-default px-2 py-1">
        <button
          onClick={() => setTab("timeline")}
          className={`rounded-t px-3 py-1 text-xs font-medium transition-colors ${
            tab === "timeline"
              ? "bg-surface text-accent border-b-2 border-accent"
              : "text-fg-muted hover:text-fg-secondary"
          }`}
        >
          Agent Timeline
        </button>
        <button
          onClick={() => setTab("anomalies")}
          className={`rounded-t px-3 py-1 text-xs font-medium transition-colors ${
            tab === "anomalies"
              ? "bg-surface text-accent border-b-2 border-accent"
              : "text-fg-muted hover:text-fg-secondary"
          }`}
        >
          Anomalies {anomalies.length > 0 && `(${anomalies.length})`}
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        {tab === "timeline" ? (
          <AgentTimeline
            events={timelineEvents}
            loading={timelineLoading}
            totalElapsedS={timelineTotal}
            iterationsUsed={timelineIters}
            finalVerdict={timelineVerdict}
            liveCursor={timelineCursor ?? null}
          />
        ) : (
          <AnomalyPanel
            anomalies={anomalies}
            loading={timelineLoading}
            onSelectTag={onSelectAnomalyTag}
          />
        )}
      </div>
    </div>
  );
}

export function App() {
  const health = useHealth();
  const { drawings, loading: drawingsLoading } = useDrawingList();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadEntry[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("pnid:sidebarCollapsed") === "1";
  });
  const [fullscreen, setFullscreen] = useState(false);
  const [querySlideOpen, setQuerySlideOpen] = useState(false);
  // Drawing key whose post-Run SearchIndex indexing failed — surfaces a
  // soft warning in the query panel (queries still work via the global
  // fallback, but the user should know grounding may be weaker).
  const [indexFailedKey, setIndexFailedKey] = useState<string | null>(null);

  // Escape key handler for fullscreen + slide-over
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (querySlideOpen) setQuerySlideOpen(false);
        else if (fullscreen) setFullscreen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen, querySlideOpen]);
  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      "pnid:sidebarCollapsed",
      sidebarCollapsed ? "1" : "0",
    );
  }, [sidebarCollapsed]);

  const stream = useExtractStream();
  const replay = usePipelineReplay(3);

  // Auto-select the first hero drawing once the list loads.
  useEffect(() => {
    if (selectedKey == null && drawings.length > 0) {
      const first = drawings[0]?.key ?? null;
      setSelectedKey(first);
    }
  }, [drawings, selectedKey]);

  // Reset both state machines whenever the drawing changes.
  useEffect(() => {
    stream.reset();
    replay.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey]);

  const isUpload = selectedKey?.startsWith("upl-") ?? false;
  // Real-industry samples currently use either `real-*` (legacy NREL)
  // or `uer-*` (DIN/EN UER drawings). Both have no cached pipeline /
  // GT geometry, so the same code path applies.
  const isRealSample =
    (selectedKey?.startsWith("real-") || selectedKey?.startsWith("uer-")) ?? false;
  // Both uploads and real-industry samples have no cached pipeline / GT
  // geometry, so we suppress those fetches to avoid a 404 round-trip and
  // to keep the canvas in its "image only, no overlay" mode.
  const skipCache = isUpload || isRealSample;
  const { pipeline } = usePipeline(skipCache ? null : selectedKey);
  const { geometry: gtGeometry, loading: geometryLoading } = useGeometry(
    skipCache ? null : selectedKey,
  );
  // For uploads + real samples, synthesize geometry from the live stream
  // result so the bbox / traveling-light overlay still renders.
  const liveGeometry = useMemo(() => {
    if (!skipCache) return null;
    if (stream.drawingKey !== selectedKey) return null;
    return liveGeometryFrom(stream.result, stream.events);
  }, [skipCache, stream.drawingKey, stream.result, stream.events, selectedKey]);
  const geometry = gtGeometry ?? liveGeometry;

  // ----- Korean NL summary + storage notice -----
  const summary = useSummary(selectedKey);
  const drawingTitle = useMemo(
    () => drawings.find((d) => d.key === selectedKey)?.title ?? null,
    [drawings, selectedKey],
  );
  const liveDone = stream.drawingKey === selectedKey && stream.status === "done";
  // Guard against showing the previous drawing's replay state for a frame
  // during a selection switch: require the cached pipeline to belong to
  // the currently-selected drawing.
  const replayDoneMatching =
    replay.status === "done" && pipeline != null && pipeline.drawing_id === selectedKey;
  const justFinishedRef = useRef<string | null>(null);
  useEffect(() => {
    // Fire summary exactly once per Run completion.
    if (!selectedKey) return;
    let result: typeof stream.result | null = null;
    let stamp = "";
    if (liveDone && stream.result) {
      result = stream.result;
      stamp = `${selectedKey}:live:${stream.result.total_elapsed_s}`;
    } else if (replayDoneMatching && pipeline) {
      result = pipeline;
      stamp = `${selectedKey}:replay:${pipeline.total_elapsed_s}`;
    }
    if (result && stamp && justFinishedRef.current !== stamp) {
      justFinishedRef.current = stamp;
      summary.generate(result, drawingTitle);
      // Index the freshly-completed extraction into the SearchIndex
      // so /api/query can answer questions about THIS drawing —
      // otherwise live-only drawings would return "Not found".
      const indexedKey = result.drawing_id;
      void api.indexRun({
        drawing_id: indexedKey,
        extraction: result.extraction,
      }).then(
        () => setIndexFailedKey((k) => (k === indexedKey ? null : k)),
        // Non-fatal — query still works via the global fallback — but
        // flag it so the panel can warn that grounding may be weaker.
        () => setIndexFailedKey(indexedKey),
      );
    }
    if (!liveDone && !replayDoneMatching) {
      justFinishedRef.current = null;
    }
  }, [
    liveDone, replayDoneMatching, stream.result, pipeline,
    selectedKey, drawingTitle, summary,
  ]);

  // Active phase: live > replay > idle.
  let phase: ReplayPhase = "idle";
  if (stream.drawingKey === selectedKey && stream.status !== "idle") {
    if (stream.status === "done") phase = "done";
    else if (stream.cursor != null && stream.cursor >= 0) {
      const ev = stream.events[stream.cursor];
      phase = ev ? stagePhase(ev.stage) : "extracting";
    } else phase = "extracting";
  } else if (replay.status !== "idle") {
    phase = replay.phase;
  }

  // Idle = neither replay nor live is running. Force timeline/anomaly empty.
  const showLive = stream.drawingKey === selectedKey && stream.status !== "idle";
  const showReplay = !showLive && replay.status !== "idle";

  // Timeline events:
  //   live → stream.events
  //   replay → cached events truncated to cursor
  //   idle → []  (the cached pipeline fetch is hidden until Run)
  const timelineEvents = showLive
    ? stream.events
    : showReplay
      ? (pipeline?.events ?? []).slice(0, replay.cursor + 1)
      : [];
  const timelineLoading = showLive ? stream.status === "connecting" : false;
  const timelineTotal = showLive
    ? stream.result?.total_elapsed_s ?? null
    : showReplay
      ? pipeline?.total_elapsed_s ?? null
      : null;
  const timelineIters = showLive
    ? stream.result?.iterations_used ?? null
    : showReplay
      ? pipeline?.iterations_used ?? null
      : null;
  const timelineVerdict = showLive
    ? stream.result?.verdict ?? null
    : showReplay
      ? pipeline?.verdict ?? null
      : null;
  const timelineCursor = showLive
    ? stream.cursor
    : showReplay
      ? replay.cursor
      : null;

  // Anomalies: live → stream.result, replay → cached pipeline, idle → []
  const anomalies = useMemo(
    () => {
      if (showLive) return stream.result?.anomalies ?? [];
      if (showReplay) return pipeline?.anomalies ?? [];
      return [];
    },
    [showLive, showReplay, stream.result, pipeline],
  );
  const anomalyTags = useMemo(() => buildAnomalyTags(anomalies), [anomalies]);

  const handleRunLive = (modifiers: { shift?: boolean } = {}) => {
    if (!selectedKey) return;
    // Uploads and real-industry samples → always real Bedrock.
    if (
      selectedKey.startsWith("upl-") ||
      selectedKey.startsWith("real-") ||
      selectedKey.startsWith("uer-")
    ) {
      replay.reset();
      stream.start(selectedKey, { sessionId: DEMO_SESSION_ID });
      return;
    }
    // Shift override → force real Bedrock.
    if (modifiers.shift) {
      replay.reset();
      stream.start(selectedKey, { sessionId: DEMO_SESSION_ID });
      return;
    }
    // No cache → must run real Bedrock (pre-staged first run).
    if (!pipeline?.events?.length) {
      replay.reset();
      stream.start(selectedKey, { sessionId: DEMO_SESSION_ID });
      return;
    }
    // Cached events → replay 3×.
    stream.reset();
    replay.start(pipeline.events);
  };

  const handleSelectSource = (drawingId: string, tag: string) => {
    if (drawingId !== selectedKey) setSelectedKey(drawingId);
    setActiveTag(tag);
  };

  const handleSelectAnomalyTag = (tag: string) => setActiveTag(tag);

  const handleUploaded = (drawingId: string, fileName: string) => {
    setUploads((u) => [...u.filter((x) => x.key !== drawingId), { key: drawingId, fileName }]);
    setSelectedKey(drawingId);
    setActiveTag(null);
  };

  return (
    <div className="flex h-screen flex-col bg-canvas text-fg-primary">
      <Header health={health} />
      <div className="flex flex-1 overflow-hidden">
        <DrawingSidebar
          drawings={drawings}
          uploads={uploads}
          loading={drawingsLoading}
          selectedKey={selectedKey}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((c) => !c)}
          onSelect={(key) => {
            stream.reset();
            replay.reset();
            setSelectedKey(key);
            setActiveTag(null);
          }}
          onUploaded={handleUploaded}
          uploadDisabled={
            stream.status === "connecting" || stream.status === "streaming"
          }
        />
        <main
          aria-label="Drawing inspector"
          className="grid flex-1 grid-cols-[minmax(0,1fr)_minmax(360px,420px)] gap-4 overflow-hidden p-4"
        >
          {/* Left column — stepper + viewer + metrics + tabbed bottom */}
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,4fr)_auto_minmax(0,1.5fr)] gap-3 overflow-hidden">
            {/* Stepper: top position when idle/done */}
            {!(showLive || showReplay) && (
              <PipelineStepper
                events={timelineEvents}
                cursor={timelineCursor ?? null}
                active={false}
                done={phase === "done"}
              />
            )}
            {/* Spacer when stepper moves to overlay during analysis */}
            {(showLive || showReplay) && <div />}

            {/* Drawing viewer */}
            <section className="relative overflow-hidden rounded-lg border border-border-default bg-surface">
              {/* Stepper: floating overlay on drawing during analysis */}
              {(showLive || showReplay) && (
                <div className="pointer-events-none absolute inset-x-0 bottom-4 z-30 flex justify-center px-4">
                  <div className="pointer-events-auto rounded-xl border border-accent/40 bg-canvas/90 px-4 py-2 shadow-lg shadow-accent/10 backdrop-blur-md">
                    <PipelineStepper
                      events={timelineEvents}
                      cursor={timelineCursor ?? null}
                      active={true}
                      done={false}
                    />
                  </div>
                </div>
              )}
              <PnidViewer
                drawingKey={selectedKey}
                geometry={geometry}
                geometryLoading={geometryLoading}
                activeTag={activeTag}
                onSelectTag={setActiveTag}
                streamStatus={stream.status}
                streamError={stream.error}
                onRunLive={handleRunLive}
                onCancelLive={stream.cancel}
                replayStatus={replay.status}
                onReplayPause={replay.pause}
                onReplayResume={replay.resume}
                onReplayReset={replay.reset}
                phase={phase}
                anomalyTags={anomalyTags}
                hallucinationTag={selectedKey === "01b" ? "PSV-101" : null}
                bannerEvents={timelineEvents}
                bannerCursor={timelineCursor ?? null}
                fullscreen={fullscreen}
                onToggleFullscreen={() => setFullscreen((f) => !f)}
              />
            </section>

            {/* Metric hero cards + summary (after Run completes) */}
            <div className="flex flex-col gap-2">
              {(liveDone || replayDoneMatching) && (
                <MetricCards result={showLive ? stream.result : pipeline} />
              )}
              {summary.status !== "idle" ? (
                <SummaryCard state={summary} />
              ) : null}
            </div>

            {/* Bottom panel — tabbed Timeline / Anomalies (collapsed height) */}
            <section className="min-h-0 overflow-hidden">
              <BottomTabs
                timelineEvents={timelineEvents}
                timelineLoading={timelineLoading}
                timelineTotal={timelineTotal}
                timelineIters={timelineIters}
                timelineVerdict={timelineVerdict}
                timelineCursor={timelineCursor}
                anomalies={anomalies}
                onSelectAnomalyTag={handleSelectAnomalyTag}
              />
            </section>
          </div>

          {/* Right column — full-height Query, scrolls independently */}
          <aside
            aria-label="Natural language query"
            className="flex min-h-0 flex-col overflow-hidden"
          >
            <QueryPanel
              drawingKey={selectedKey}
              suggestedQueries={summary.suggestedQueries}
              onSelectSource={handleSelectSource}
              runReady={liveDone || replayDoneMatching}
              geometry={geometry}
              indexWarning={indexFailedKey === selectedKey}
            />
          </aside>
        </main>
      </div>

      {/* Fullscreen overlay — covers everything when active */}
      {fullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-canvas">
          {/* Stepper at top */}
          <div className="flex items-center justify-between border-b border-border-default px-4 py-2">
            <PipelineStepper
              events={timelineEvents}
              cursor={timelineCursor ?? null}
              active={showLive || showReplay}
              done={phase === "done"}
            />
            <button
              type="button"
              aria-label="Exit fullscreen"
              onClick={() => setFullscreen(false)}
              className="rounded-md border border-border-default bg-surface px-2 py-1 text-xs text-fg-secondary hover:bg-raised hover:text-fg-primary"
            >
              Esc
            </button>
          </div>

          {/* Viewer fills remaining space */}
          <div className="relative flex-1 overflow-hidden">
            <PnidViewer
              drawingKey={selectedKey}
              geometry={geometry}
              geometryLoading={geometryLoading}
              activeTag={activeTag}
              onSelectTag={setActiveTag}
              streamStatus={stream.status}
              streamError={stream.error}
              onRunLive={handleRunLive}
              onCancelLive={stream.cancel}
              replayStatus={replay.status}
              onReplayPause={replay.pause}
              onReplayResume={replay.resume}
              onReplayReset={replay.reset}
              phase={phase}
              anomalyTags={anomalyTags}
              hallucinationTag={selectedKey === "01b" ? "PSV-101" : null}
              bannerEvents={timelineEvents}
              bannerCursor={timelineCursor ?? null}
              fullscreen
              onToggleFullscreen={() => setFullscreen(false)}
            />

            {/* Chat bubble button (right side, below toolbar to avoid Run overlap) */}
            <button
              type="button"
              aria-label="Open query panel"
              onClick={() => setQuerySlideOpen((o) => !o)}
              className="absolute right-4 top-16 z-40 flex h-10 w-10 items-center justify-center rounded-full border border-accent/50 bg-surface/90 text-accent shadow-lg backdrop-blur-sm transition hover:scale-110 hover:bg-accent/20"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </button>
          </div>

          {/* Metric cards + summary at bottom (after done) */}
          {(liveDone || replayDoneMatching) && (
            <div className="max-h-[30vh] overflow-y-auto border-t border-border-default px-4 py-2">
              <MetricCards result={showLive ? stream.result : pipeline} />
              {summary.status !== "idle" && (
                <div className="mt-2">
                  <SummaryCard state={summary} />
                </div>
              )}
            </div>
          )}

          {/* Slide-over Query panel */}
          {querySlideOpen && (
            <div
              className="fixed inset-y-0 right-0 z-[60] flex"
              onClick={(e) => { if (e.target === e.currentTarget) setQuerySlideOpen(false); }}
            >
              <div
                className="ml-auto h-full w-[380px] border-l border-border-default bg-surface/95 shadow-2xl backdrop-blur-md"
                style={{ animation: "slideInRight 0.25s ease-out" }}
              >
                <div className="flex h-full flex-col p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold text-fg-secondary">Natural-Language Query</span>
                    <button
                      type="button"
                      onClick={() => setQuerySlideOpen(false)}
                      className="rounded p-1 text-fg-muted hover:bg-raised hover:text-fg-primary"
                      aria-label="Close"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
                    </button>
                  </div>
                  <div className="min-h-0 flex-1">
                    <QueryPanel
                      drawingKey={selectedKey}
                      suggestedQueries={summary.suggestedQueries}
                      onSelectSource={handleSelectSource}
                      runReady={liveDone || replayDoneMatching}
                      geometry={geometry}
                      indexWarning={indexFailedKey === selectedKey}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
