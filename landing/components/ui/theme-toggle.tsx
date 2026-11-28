"use client";

// Toggle claro/oscuro (next-themes). Ícono sol/luna, estilo del sistema v7.
// El tema real solo se conoce en cliente; el snapshot de useSyncExternalStore
// evita el desajuste de hidratación.

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { cn } from "@/lib/utils";

const suscribirNada = () => () => {};

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  // En el servidor el tema aún no existe; en el cliente sí. Evita el
  // desajuste de hidratación sin un setState dentro de un efecto.
  const mounted = useSyncExternalStore(suscribirNada, () => true, () => false);
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
