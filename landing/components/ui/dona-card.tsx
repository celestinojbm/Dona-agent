"use client";

// Card del sistema visual de la app (0A). Superficie elevada con borde de luz.
// Consume los tokens de dona-app-tokens.css.

import * as React from "react";
import { cn } from "@/lib/utils";

export interface DonaCardProps extends React.HTMLAttributes<HTMLDivElement> {
  compacta?: boolean;
}

export const DonaCard = React.forwardRef<HTMLDivElement, DonaCardProps>(
  ({ className, compacta, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("dona-card", compacta && "dona-card--compact", className)}
      {...props}
    />
  ),
);
DonaCard.displayName = "DonaCard";
