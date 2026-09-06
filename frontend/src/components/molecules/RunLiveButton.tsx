import { Loader2, Pause, Play, Square } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import type { ReplayStatus } from "@/hooks/usePipelineReplay";
import type { StreamStatus } from "@/hooks/useExtractStream";

interface Props {
  liveStatus: StreamStatus;
  replayStatus: ReplayStatus;
  /** modifier-aware handler: receives shiftKey to pick the live branch. */
  onClick: (modifiers: { shift: boolean }) => void;
  onCancelLive: () => void;
  onPauseReplay: () => void;
  onResumeReplay: () => void;
  onResetReplay: () => void;
  disabled?: boolean;
}

/**
 * Single "Run Live" button that drives both the cached replay path
 * (default click) and the real Bedrock streaming path (shift-click,
 * presenter shortcut). The icon and label morph based on which state
 * machine is active.
 */
export function RunLiveButton({
  liveStatus, replayStatus, onClick, onCancelLive,
  onPauseReplay, onResumeReplay, onResetReplay, disabled,
}: Props) {
  const liveInFlight =
    liveStatus === "connecting" || liveStatus === "streaming";

  if (liveInFlight) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={onCancelLive}
        aria-label="Cancel live extraction"
      >
        <Loader2 aria-hidden className="animate-spin" size={14} />
        <span>Cancel</span>
        <Square aria-hidden size={12} />
      </Button>
    );
  }

  if (replayStatus === "playing") {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={onPauseReplay}
        aria-label="Pause extraction replay"
      >
        <Pause aria-hidden size={14} />
        <span>Pause</span>
      </Button>
    );
  }
  if (replayStatus === "paused") {
    return (
      <Button
        variant="solid"
        size="sm"
        onClick={onResumeReplay}
        aria-label="Resume extraction"
      >
        <Play aria-hidden size={14} />
        <span>Resume</span>
      </Button>
    );
  }
  if (replayStatus === "done") {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={onResetReplay}
        aria-label="Run again"
      >
        <Play aria-hidden size={14} />
        <span>Run again</span>
      </Button>
    );
  }
  return (
    <Button
      variant="solid"
      size="sm"
      onClick={(e) => onClick({ shift: e.shiftKey })}
      disabled={disabled}
      aria-label="Run live extraction"
      title="Click to extract (Shift+Click for real Bedrock invocation)"
    >
      <Play aria-hidden size={14} />
      <span>Run Live</span>
    </Button>
  );
}
