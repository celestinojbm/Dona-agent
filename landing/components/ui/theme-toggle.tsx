"use client";

// Toggle claro/oscuro (next-themes). Ícono sol/luna, estilo del sistema v7.
// El guard `mounted` evita el desajuste de hidratación (el tema real solo se
// conoce en cliente).

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
      className={cn(
        "grid h-9 w-9 cursor-pointer place-items-center rounded-full border border-[color:var(--line)] text-[color:var(--ink-2)] transition-colors hover:text-[color:var(--ink)]",
        className,
      )}
    >
      {mounted && isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
