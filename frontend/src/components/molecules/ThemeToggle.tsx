import { Moon, Sun } from "lucide-react";

import { IconButton } from "@/components/atoms/IconButton";
import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const nextLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  return (
    <IconButton
      aria-label={nextLabel}
      title={nextLabel}
      onClick={toggle}
    >
      {theme === "dark" ? <Sun aria-hidden size={18} /> : <Moon aria-hidden size={18} />}
    </IconButton>
  );
}
