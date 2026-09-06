/**
 * Stage catalog — central place to map orchestrator `ProgressEvent.stage`
 * names to human labels, lucide icons, and tones.
 *
 * Backend stages (backend/agents/strands_orchestrator.py):
 *   - render
 *   - extract
 *   - evaluate
 *   - self_correct_initial_extract
 *   - self_correct_error_analysis
 *   - self_correct_reextract
 *   - self_correct_re_evaluate
 *   - self_correct_hold
 *   - self_correct_done
 *   - finalize
 */
import type { LucideIcon } from "lucide-react";
import {
  Brain,
  CheckCircle2,
  CircleDashed,
  Eye,
  FileImage,
  Hand,
  Repeat,
  RotateCcw,
  ScanSearch,
  Wand2,
} from "lucide-react";

export type StageGroup = "main" | "self_correct";

export interface StageMeta {
  group: StageGroup;
  label: string;
  icon: LucideIcon;
  tone: "neutral" | "accent" | "success" | "warning" | "danger";
}

const REGISTRY: Record<string, StageMeta> = {
  render: {
    group: "main",
    label: "Render",
    icon: FileImage,
    tone: "neutral",
  },
  extract: {
    group: "main",
    label: "Extract (Vision)",
    icon: ScanSearch,
    tone: "accent",
  },
  evaluate: {
    group: "main",
    label: "Evaluate (Critic)",
    icon: Eye,
    tone: "accent",
  },
  finalize: {
    group: "main",
    label: "Finalize",
    icon: CheckCircle2,
    tone: "success",
  },
  self_correct_initial_extract: {
    group: "self_correct",
    label: "Initial Extract (snapshot)",
    icon: CircleDashed,
    tone: "neutral",
  },
  self_correct_error_analysis: {
    group: "self_correct",
    label: "Error Analyzer",
    icon: Brain,
    tone: "warning",
  },
  self_correct_reextract: {
    group: "self_correct",
    label: "Re-extract",
    icon: RotateCcw,
    tone: "accent",
  },
  self_correct_re_evaluate: {
    group: "self_correct",
    label: "Re-evaluate",
    icon: Eye,
    tone: "accent",
  },
  self_correct_hold: {
    group: "self_correct",
    label: "Hold (genuine anomalies)",
    icon: Hand,
    tone: "warning",
  },
  self_correct_done: {
    group: "self_correct",
    label: "Self-correction Done",
    icon: Wand2,
    tone: "success",
  },
};

const FALLBACK: StageMeta = {
  group: "main",
  label: "Step",
  icon: Repeat,
  tone: "neutral",
};

export function stageMeta(stage: string): StageMeta {
  return REGISTRY[stage] ?? FALLBACK;
}

/**
 * Verdict transitions can come back as "" (empty) on intermediate
 * sub-stages. Map to a friendly label or null.
 */
export function verdictLabel(v: string | undefined | null): string | null {
  if (!v) return null;
  switch (v) {
    case "pass":
      return "pass";
    case "needs_correction":
      return "needs correction";
    default:
      return v;
  }
}
