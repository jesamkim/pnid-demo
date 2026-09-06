/**
 * P&ID viewer — drawing image + phase-aware SVG overlay + a small
 * top toolbar with Run-Live, Replay, and Pause controls.
 *
 * The overlay is hidden by default (`phase === "idle"`) so the user
 * sees the raw drawing first, then triggers a Replay (cached, free) or
 * Run Live (real Bedrock call) to walk through the agentic stages.
 */
import { Expand, ImageOff, Loader2, Maximize2, Minimize2, Minus, Plus, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/api/client";
import { Badge } from "@/components/atoms/Badge";
import { RunLiveButton } from "@/components/molecules/RunLiveButton";
import { PnidOverlay } from "@/components/organisms/PnidOverlay";
import { PnidStepBanner } from "@/components/organisms/PnidStepBanner";
import { cn } from "@/lib/cn";
import type { GeometryResponse, ProgressEvent } from "@/api/types";
import type { ReplayPhase, ReplayStatus } from "@/hooks/usePipelineReplay";
import type { StreamStatus } from "@/hooks/useExtractStream";

interface Props {
  drawingKey: string | null;
  geometry: GeometryResponse | null;
  geometryLoading: boolean;
  activeTag: string | null;
  onSelectTag: (tag: string | null) => void;
  // Live extraction
  streamStatus: StreamStatus;
  streamError: string | null;
  onRunLive: (modifiers?: { shift: boolean }) => void;
  onCancelLive: () => void;
  // Replay
  replayStatus: ReplayStatus;
  onReplayPause: () => void;
  onReplayResume: () => void;
  onReplayReset: () => void;
  // Phase (drives overlay)
  phase: ReplayPhase;
  anomalyTags: ReadonlySet<string>;
  hallucinationTag?: string | null;
  // StepBanner data
  bannerEvents: ProgressEvent[];
  bannerCursor: number | null;
  // Fullscreen
  fullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

export function PnidViewer(props: Props) {
  const {
    drawingKey, geometry, geometryLoading,
    activeTag, onSelectTag,
    streamStatus, streamError, onRunLive, onCancelLive,
    replayStatus, onReplayPause, onReplayResume, onReplayReset,
    phase, anomalyTags, hallucinationTag,
    bannerEvents, bannerCursor,
    fullscreen, onToggleFullscreen,
  } = props;
  const bannerActive =
    streamStatus === "connecting" || streamStatus === "streaming"
    || replayStatus === "playing" || replayStatus === "paused";
  const bannerDone =
    streamStatus === "done" || replayStatus === "done";

  // Track load state BY drawing key, not as a bare boolean. The reset
  // effect runs after `drawingKey` changes, so a bare boolean would let
  // one render pair the new image src with the previous `loaded=true`,
  // flashing a stale overlay. Deriving `loaded` from the key closes that
  // gap — the image/overlay only shows once THIS key has actually loaded.
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [erroredKey, setErroredKey] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const loaded = loadedKey === drawingKey;
  const errored = erroredKey === drawingKey;

  useEffect(() => {
    setZoom(1);  // reset zoom when drawing changes
  }, [drawingKey]);

  const zoomStep = 0.25;
  const zoomMin = 0.5;
  const zoomMax = 4;
  const zoomIn = () => setZoom((z) => Math.min(zoomMax, Math.round((z + zoomStep) * 100) / 100));
  const zoomOut = () => setZoom((z) => Math.max(zoomMin, Math.round((z - zoomStep) * 100) / 100));
  const zoomReset = () => setZoom(1);
  const zoomFit = () => setZoom(1);

  // ----- mouse drag-to-pan inside the overflow-auto container -----
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{
    sx: number; sy: number; left: number; top: number;
  } | null>(null);
  const [dragging, setDragging] = useState(false);

  const onMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;          // left button only
    const el = scrollRef.current;
    if (!el) return;
    // Only initiate pan when there's actually somewhere to scroll —
    // otherwise we'd block clicks on the equipment overlay.
    const canPan =
      el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight;
    if (!canPan) return;
    dragRef.current = {
      sx: e.clientX, sy: e.clientY,
      left: el.scrollLeft, top: el.scrollTop,
    };
    setDragging(true);
  };
  const onMouseMove = (e: React.MouseEvent) => {
    const d = dragRef.current;
    const el = scrollRef.current;
    if (!d || !el) return;
    el.scrollLeft = d.left - (e.clientX - d.sx);
    el.scrollTop = d.top - (e.clientY - d.sy);
  };
  const stopDrag = () => {
    if (dragRef.current) {
      dragRef.current = null;
      setDragging(false);
    }
  };

  if (!drawingKey) {
    return (
      <div role="status" className="flex h-full items-center justify-center text-fg-muted">
        Select a drawing from the sidebar to begin.
      </div>
    );
  }

  const showOverlay = phase !== "idle" && geometry;
  const liveInFlight = streamStatus === "connecting" || streamStatus === "streaming";
  const replayDisabled = liveInFlight;
  const liveDisabled = replayStatus === "playing" || replayStatus === "paused";

  return (
    <div
      role="region"
      aria-label={`P&ID viewer for drawing ${drawingKey}`}
      className="relative flex h-full w-full flex-col overflow-hidden bg-canvas"
    >
      <div className="flex items-center justify-between gap-3 border-b border-border-default bg-surface px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-fg-primary">
            {drawingKey}
          </span>
          <PhaseBadge phase={phase} replayStatus={replayStatus} />
          {streamStatus === "streaming" || streamStatus === "connecting" ? (
            <Badge tone="accent">live extraction</Badge>
          ) : streamStatus === "error" ? (
            <Badge tone="danger">live error</Badge>
          ) : null}
          {streamError ? (
            <span className="text-xs text-danger" aria-live="polite">{streamError}</span>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <div
            role="group"
            aria-label="Zoom"
            className="flex items-center gap-0.5 rounded-md border border-border-default bg-surface px-1 py-0.5 text-fg-secondary"
          >
            <button
              type="button"
              aria-label="Zoom out"
              onClick={zoomOut}
              disabled={zoom <= zoomMin}
              className="rounded p-1 transition hover:bg-raised hover:text-accent disabled:opacity-40"
            >
              <Minus aria-hidden size={14} />
            </button>
            <span
              aria-live="polite"
              className="min-w-[3rem] text-center font-mono text-xs text-fg-muted"
            >
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              aria-label="Zoom in"
              onClick={zoomIn}
              disabled={zoom >= zoomMax}
              className="rounded p-1 transition hover:bg-raised hover:text-accent disabled:opacity-40"
            >
              <Plus aria-hidden size={14} />
            </button>
            <button
              type="button"
              aria-label="Reset zoom"
              onClick={zoomReset}
              disabled={zoom === 1}
              className="rounded p-1 transition hover:bg-raised hover:text-accent disabled:opacity-40"
            >
              <RotateCcw aria-hidden size={14} />
            </button>
            <button
              type="button"
              aria-label="Fit to view"
              onClick={zoomFit}
              className="rounded p-1 transition hover:bg-raised hover:text-accent"
            >
              <Maximize2 aria-hidden size={14} />
            </button>
            {onToggleFullscreen && (
              <button
                type="button"
                aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
                onClick={onToggleFullscreen}
                className="rounded p-1 transition hover:bg-raised hover:text-accent"
              >
                {fullscreen ? <Minimize2 aria-hidden size={14} /> : <Expand aria-hidden size={14} />}
              </button>
            )}
          </div>
          <RunLiveButton
            liveStatus={streamStatus}
            replayStatus={replayStatus}
            onClick={onRunLive}
            onCancelLive={onCancelLive}
            onPauseReplay={onReplayPause}
            onResumeReplay={onReplayResume}
            onResetReplay={onReplayReset}
            disabled={replayDisabled || liveDisabled}
          />
        </div>
      </div>

      <div className="relative flex flex-1 overflow-hidden">
        {/* Banner is rendered as a sibling of the scroll container so
            it stays pinned to the viewer (not to the panned drawing).
            z-30 keeps it above the image / overlay; pointer-events
            none on the inner positioner means the user can still pan
            the drawing under the banner. */}
        <div className="pointer-events-none absolute inset-x-0 top-3 z-30 flex justify-center px-4">
          <PnidStepBanner
            events={bannerEvents}
            cursor={bannerCursor}
            active={bannerActive}
            done={bannerDone}
            standalone
          />
        </div>
        {/* Analysis-in-progress dim overlay — makes the drawing slightly
            darker so the floating stepper + step banner stand out more */}
        {(bannerActive && !bannerDone) && (
          <div className="pointer-events-none absolute inset-0 z-10 bg-black/30 transition-opacity duration-500" />
        )}

        {/* Color legend — visible only when overlay is active */}
        {phase !== "idle" && (
          <div className="pointer-events-none absolute bottom-3 right-3 z-20 flex gap-2 rounded-md border border-border-default bg-surface/90 px-2 py-1 text-[9px] font-medium backdrop-blur-sm">
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-[#00d4ff]" />Equipment</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-[#f59e0b]" />Instrument</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-[#f97316]" />Valve</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm bg-[#64748b]" />Line</span>
          </div>
        )}

        <div
          ref={scrollRef}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={stopDrag}
          onMouseLeave={stopDrag}
          className={cn(
            "relative flex flex-1 items-center justify-center overflow-auto p-4",
            dragging ? "cursor-grabbing select-none" : zoom > 1 ? "cursor-grab" : "",
          )}
        >
        {!loaded && !errored ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-fg-muted">
            <Loader2 aria-hidden className="animate-spin" size={20} />
            <span className="sr-only">Loading drawing</span>
          </div>
        ) : null}

        {errored ? (
          <div className="flex flex-col items-center gap-2 text-fg-muted">
            <ImageOff aria-hidden size={20} />
            <p className="text-sm">Could not load drawing image.</p>
          </div>
        ) : geometry ? (
          <div
            className={cn(
              "relative shrink-0",
              loaded ? "opacity-100" : "opacity-0",
              "transition-opacity duration-[var(--motion-base)]",
            )}
            style={{
              aspectRatio: `${geometry.canvas.width} / ${geometry.canvas.height}`,
              width:
                `calc(min(100%, (100vh - 14rem) * ${geometry.canvas.width} / ${geometry.canvas.height}) * ${zoom})`,
              transition: "width var(--motion-fast) ease-out",
            }}
          >
            <img
              key={drawingKey}
              src={api.imageUrl(drawingKey, 150)}
              alt={`P&ID drawing ${drawingKey}`}
              className="absolute inset-0 h-full w-full select-none object-contain"
              onLoad={() => setLoadedKey(drawingKey)}
              onError={() => setErroredKey(drawingKey)}
              draggable={false}
            />
            {loaded && showOverlay ? (
              <PnidOverlay
                geometry={geometry}
                activeTag={activeTag}
                onSelectTag={onSelectTag}
                phase={phase}
                anomalyTags={anomalyTags}
                hallucinationTag={hallucinationTag}
              />
            ) : null}
            {loaded && !showOverlay ? (
              <div className="pointer-events-none absolute inset-x-0 top-3 flex justify-center">
                <span className="rounded-full bg-[var(--accent-soft)] px-3 py-1 text-xs font-semibold text-accent">
                  ▶ Click <strong>Replay</strong> or <strong>Run Live</strong> to extract
                </span>
              </div>
            ) : null}
          </div>
        ) : (
          <img
            key={drawingKey}
            src={api.imageUrl(drawingKey, 150)}
            alt={`P&ID drawing ${drawingKey}`}
            className={cn(
              "select-none object-contain transition-opacity duration-[var(--motion-base)]",
              loaded ? "opacity-100" : "opacity-0",
            )}
            style={{
              maxHeight: `calc((100vh - 14rem) * ${zoom})`,
              maxWidth: `calc(100% * ${zoom})`,
              transition: "max-height var(--motion-fast) ease-out, max-width var(--motion-fast) ease-out",
            }}
            onLoad={() => setLoadedKey(drawingKey)}
            onError={() => setErroredKey(drawingKey)}
            draggable={false}
          />
        )}

        {geometryLoading ? (
          <span className="sr-only">Loading geometry overlay</span>
        ) : null}
        </div>  {/* /scroll container */}
      </div>  {/* /viewer body wrapper */}
    </div>
  );
}

function PhaseBadge({
  phase, replayStatus,
}: {
  phase: ReplayPhase;
  replayStatus: ReplayStatus;
}) {
  if (replayStatus === "idle" && phase === "idle") return null;
  const labels: Record<ReplayPhase, string> = {
    idle: "idle",
    extracting: "extracting",
    evaluating: "evaluating",
    self_correcting: "self-correcting",
    finalizing: "finalizing",
    done: "complete",
  };
  const tones: Record<ReplayPhase, "neutral" | "accent" | "warning" | "success"> = {
    idle: "neutral",
    extracting: "accent",
    evaluating: "accent",
    self_correcting: "warning",
    finalizing: "warning",
    done: "success",
  };
  return <Badge tone={tones[phase]}>{labels[phase]}</Badge>;
}
