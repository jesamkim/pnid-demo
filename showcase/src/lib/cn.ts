/**
 * `cn()` — clsx + tailwind-merge wrapper.
 *
 * Used by all atom-level components to compose Tailwind classes safely
 * (later utility wins) while accepting conditional / null / undefined inputs.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
