"use client";

// Campo de formulario accesible del sistema de la app (0A). Asocia <label> con
// el control por id, expone aria-invalid y un mensaje de error con
// aria-describedby. Consume los tokens de dona-app-tokens.css.

import * as React from "react";
import { cn } from "@/lib/utils";

export interface DonaFieldProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string;
  error?: string;
}

export const DonaField = React.forwardRef<HTMLInputElement, DonaFieldProps>(
  ({ id, etiqueta, error, className, ...props }, ref) => {
    const generatedId = React.useId();
    const campoId = id ?? generatedId;
    const errorId = `${campoId}-error`;
    return (
      <div className="dona-field">
        <label htmlFor={campoId} className="dona-label">
          {etiqueta}
        </label>
        <input
          ref={ref}
          id={campoId}
          className={cn("dona-input", className)}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={error ? errorId : undefined}
          {...props}
        />
        {error ? (
          <p id={errorId} role="alert" className="dona-caption" style={{ color: "var(--danger)" }}>
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
DonaField.displayName = "DonaField";
