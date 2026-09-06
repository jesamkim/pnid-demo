import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const badgeStyles = cva(
  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      tone: {
        neutral: "bg-subtle text-fg-secondary",
        accent: "bg-[var(--accent-soft)] text-accent",
        success: "bg-[color-mix(in_oklab,var(--success)_18%,transparent)] text-success",
        warning: "bg-[color-mix(in_oklab,var(--warning)_18%,transparent)] text-warning",
        danger: "bg-[color-mix(in_oklab,var(--danger)_18%,transparent)] text-danger",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeStyles> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeStyles({ tone }), className)} {...props} />;
}
