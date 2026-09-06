/**
 * Icon-only button. Always requires `aria-label` for screen readers
 * (icons are ambiguous without context — see WCAG 2.2 SC 4.1.2).
 */
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  "aria-label": string; // intentionally required
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton({ className, ...props }, ref) {
    return (
      <button
        ref={ref}
        type="button"
        className={cn(
          "inline-flex h-9 w-9 items-center justify-center rounded-md " +
            "text-fg-secondary transition-colors duration-[var(--motion-fast)] " +
            "hover:bg-subtle hover:text-fg-primary " +
            "disabled:cursor-not-allowed disabled:opacity-50 " +
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
          className,
        )}
        {...props}
      />
    );
  },
);
