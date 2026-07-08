"use client";

// Provider de tema (next-themes) para el toggle claro/oscuro app-wide.
// attribute="class" → alterna la clase `.dark` en <html>. defaultTheme claro
// (la dirección definitiva de Dona es clara; el oscuro es opt-in).

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

export function ThemeProvider({
  children,
  ...props
}: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
