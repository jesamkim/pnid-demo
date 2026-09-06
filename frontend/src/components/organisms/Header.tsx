import { GitBranch } from "lucide-react";

import { Badge } from "@/components/atoms/Badge";
import { ThemeToggle } from "@/components/molecules/ThemeToggle";
import type { Health } from "@/api/types";

interface Props {
  health: Health | null;
}

export function Header({ health }: Props) {
  return (
    <header
      className="flex h-14 items-center justify-between border-b border-border-default bg-surface px-5"
      role="banner"
    >
      <div className="flex items-center gap-3">
        {/* Official Amazon Bedrock AgentCore service icon (200×200 PNG). */}
        <img
          src="/agentcore-logo.png"
          alt="Amazon Bedrock AgentCore"
          width={28}
          height={28}
          className="select-none"
          draggable={false}
        />
        <h1 className="relative text-base font-semibold tracking-tight text-fg-primary">
          P&amp;ID Agentic Demo
          {/* The single AWS-orange accent in the entire UI — a 2px
              underline gradient that anchors the brand without competing
              with the cinematic cyan accents elsewhere. */}
          <span
            aria-hidden
            className="absolute -bottom-1 left-0 h-[2px] w-full"
            style={{
              background:
                "linear-gradient(90deg, var(--aws-orange) 0%, var(--accent) 70%, transparent 100%)",
            }}
          />
        </h1>
        <Badge tone="accent">
          <GitBranch aria-hidden size={11} />
          Bedrock AgentCore + Strands
        </Badge>
      </div>
      <div className="flex items-center gap-3">
        {health ? (
          <span className="hidden text-xs text-fg-muted sm:inline">
            memory: {health.memory_backend} / {health.drawings.length} drawings
          </span>
        ) : null}
        <ThemeToggle />
      </div>
    </header>
  );
}
