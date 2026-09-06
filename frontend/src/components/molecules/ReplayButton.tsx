import { Loader2, Pause, Play, RotateCcw } from "lucide-react";

import { Button } from "@/components/atoms/Button";
import type { ReplayStatus } from "@/hooks/usePipelineReplay";

interface Props {
  status: ReplayStatus;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onReset: () => void;
  disabled?: boolean;
}

export function ReplayButton({
  status, onStart, onPause, onResume, onReset, disabled,
}: Props) {
  if (status === "playing") {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={onPause}
        aria-label="Pause replay"
      >
        <Pause aria-hidden size={14} />
        <span>Pause</span>
      </Button>
    );
  }
  if (status === "paused") {
    return (
      <Button
        variant="solid"
        size="sm"
        onClick={onResume}
        aria-label="Resume replay"
      >
        <Loader2 aria-hidden className="animate-spin" size={14} />
        <span>Resume</span>
      </Button>
    );
  }
  if (status === "done") {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={onReset}
        aria-label="Reset replay"
      >
        <RotateCcw aria-hidden size={14} />
        <span>Reset</span>
      </Button>
    );
  }
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onStart}
      disabled={disabled}
      aria-label="Replay extraction (cached)"
    >
      <Play aria-hidden size={14} />
      <span>Replay</span>
    </Button>
  );
}
