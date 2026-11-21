"use client";

// Botón accesible del sistema visual de la app (0A). Consume los tokens de
// dona-app-tokens.css (scope [data-dona-surface="app"]). Target >=44px, foco
// visible por --ring-focus, estados disabled con semántica nativa.

import * as React from "react";
import { cn } from "@/lib/utils";

type Variante = "primary" | "ghost" | "danger";

export interface DonaButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
}

const CLASE_VARIANTE: Record<Variante, string> = {
  primary: "dona-btn--primary",
  ghost: "dona-btn--ghost",
  danger: "dona-btn--danger",
};

export const DonaButton = React.forwardRef<HTMLButtonElement, DonaButtonProps>(
  ({ className, variante = "primary", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn("dona-btn", CLASE_VARIANTE[variante], className)}
      {...props}
    />
  ),
);
DonaButton.displayName = "DonaButton";
