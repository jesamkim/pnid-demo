/**
 * Compact Amazon Bedrock / AgentCore-inspired mark.
 *
 * Drawn inline so we don't take a runtime dependency on the AWS icon
 * package. The shape mimics the published Bedrock service icon: a
 * rounded square with three orbiting nodes and a central core.
 */
import type { SVGProps } from "react";

export function BedrockMark({
  size = 22,
  className,
  ...props
}: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="Amazon Bedrock AgentCore"
      className={className}
      {...props}
    >
      <defs>
        <linearGradient id="bedrock-mark-fill" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0a1424" />
          <stop offset="100%" stopColor="#16213e" />
        </linearGradient>
        {/* Radial glow under the central core, gives the mark a
            cinematic-tech "powered" feel. */}
        <radialGradient id="bedrock-mark-core" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#a7f0ff" stopOpacity="1" />
          <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.95" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.4" />
        </radialGradient>
      </defs>
      {/* Squircle backplate */}
      <rect
        x="1.5"
        y="1.5"
        width="29"
        height="29"
        rx="6.5"
        fill="url(#bedrock-mark-fill)"
        stroke="var(--accent)"
        strokeWidth="1.2"
      />
      {/* Central core (radial gradient gives the cinematic glow feel) */}
      <circle cx="16" cy="16" r="3.6" fill="url(#bedrock-mark-core)" />
      {/* Orbiting nodes */}
      <circle cx="16" cy="6.5" r="1.7" fill="var(--accent)" />
      <circle cx="24.5" cy="20.5" r="1.7" fill="var(--accent)" />
      <circle cx="7.5" cy="20.5" r="1.7" fill="var(--accent)" />
      {/* Connecting lines */}
      <g stroke="var(--accent)" strokeWidth="1" fill="none" opacity="0.85">
        <line x1="16" y1="8.2" x2="16" y2="12.6" />
        <line x1="22.9" y1="19.5" x2="19" y2="17.6" />
        <line x1="9.1" y1="19.5" x2="13" y2="17.6" />
      </g>
    </svg>
  );
}
