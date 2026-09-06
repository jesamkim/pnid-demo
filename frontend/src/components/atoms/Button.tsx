/**
 * Button atom — variant-based styling using `cva`.
 *
 * Variants:
 *   - solid (primary action, accent background)
 *   - outline (secondary action, surface background + border)
 *   - ghost (low-emphasis, transparent)
 *
 * Sizes follow the 4px spacing grid. All variants meet WCAG AA contrast
 * against their paired surface tokens.
 */
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "@radix-ui/react-slot";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-medium " +
    "transition-colors duration-[var(--motion-fast)] " +
    "disabled:cursor-not-allowed disabled:opacity-50 " +
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
  {
    variants: {
      variant: {
        solid:
          "bg-accent text-accent-fg hover:bg-accent-strong " +
          "shadow-[var(--shadow-card)]",
        outline:
          "border border-border-strong bg-surface text-fg-primary " +
          "hover:bg-raised",
        ghost: "bg-transparent text-fg-secondary hover:bg-subtle",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-5 text-base",
      },
    },
    defaultVariants: { variant: "solid", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonStyles> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { className, variant, size, asChild = false, ...props },
    ref,
  ) {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonStyles({ variant, size }), className)}
        {...props}
      />
    );
  },
);
