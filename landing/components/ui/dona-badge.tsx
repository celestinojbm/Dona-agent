"use client";

// Badge/chip de estado del sistema visual de la app (0A). Consume los tokens de
// dona-app-tokens.css. Para estados cuyo significado va sólo por color, pasa un
// texto accesible (no comuniques estado sólo con color).

import * as React from "react";
import { cn } from "@/lib/utils";

type Tono = "neutral" | "danger" | "warning";

export interface DonaBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tono?: Tono;
}

const CLASE_TONO: Record<Tono, string> = {
  neutral: "",
  danger: "dona-badge--danger",
  warning: "dona-badge--warning",
};

export const DonaBadge = React.forwardRef<HTMLSpanElement, DonaBadgeProps>(
  ({ className, tono = "neutral", ...props }, ref) => (
    <span
      ref={ref}
      className={cn("dona-badge", CLASE_TONO[tono], className)}
      {...props}
    />
  ),
);
DonaBadge.displayName = "DonaBadge";
