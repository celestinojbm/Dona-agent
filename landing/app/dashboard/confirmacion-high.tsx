"use client";

// landing/app/dashboard/confirmacion-high.tsx
//
// Flujo de confirmación dedicada para acciones HIGH aprobadas · extraído
// del Centro de acción para que lo compartan la tarjeta de la lista y el
// panel de detalle sin duplicar el contrato con el backend.
//
// El preview y la confirmación literal ("ENVIAR") salen del backend:
//   POST /api/automation/acciones/:id/high-preview
//   POST /api/automation/acciones/:id/high-confirmar  { confirmacion }

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import type { HighPreviewResponse } from "@/lib/automation-types";

export interface ConfirmacionHighApi {
  preview: HighPreviewResponse | null;
  confirmacion: string;
  setConfirmacion: (valor: string) => void;
  busy: boolean;
  cargarPreview: () => Promise<void>;
  confirmar: () => Promise<void>;
  cerrar: () => void;
}

/**
 * Estado + llamadas del flujo HIGH. `onConfirmada` se ejecuta tras un
 * high-confirmar exitoso para que el llamador refresque la acción.
 */
export function useConfirmacionHigh(
  accionId: number,
  onConfirmada?: () => Promise<void> | void,
): ConfirmacionHighApi {
  const [preview, setPreview] = useState<HighPreviewResponse | null>(null);
  const [confirmacion, setConfirmacion] = useState("");
  const [busy, setBusy] = useState(false);

  const cargarPreview = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetch(`/api/automation/acciones/${accionId}/high-preview`, {
        method: "POST",
      });
      if (!res.ok) {
        toast.error("No pudimos cargar el preview HIGH. Intenta de nuevo.");
        return;
      }
      const data = (await res.json()) as HighPreviewResponse;
      setPreview(data);
      setConfirmacion("");
    } catch {
      toast.error("Error de conexión al cargar preview HIGH.");
    } finally {
      setBusy(false);
    }
  }, [accionId]);

  const cerrar = useCallback(() => {
    setPreview(null);
    setConfirmacion("");
  }, []);

  const confirmar = useCallback(async () => {
    if (confirmacion !== "ENVIAR") return;
    setBusy(true);
    try {
      const res = await fetch(
        `/api/automation/acciones/${accionId}/high-confirmar`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmacion }),
        },
      );
      if (!res.ok) {
        toast.error(
          "No pudimos confirmar esta acción HIGH. Revisa su estado e intenta de nuevo.",
        );
        return;
      }
      setPreview(null);
      setConfirmacion("");
      await onConfirmada?.();
    } catch {
      toast.error("Error de conexión al confirmar acción HIGH.");
    } finally {
      setBusy(false);
    }
  }, [accionId, confirmacion, onConfirmada]);

  return {
    preview,
    confirmacion,
    setConfirmacion,
    busy,
    cargarPreview,
    confirmar,
    cerrar,
  };
}

interface PanelPreviewHighProps {
  api: ConfirmacionHighApi;
  accionId: number;
}

/** Bloque de preview + confirmación literal del flujo HIGH. */
export function PanelPreviewHigh({ api, accionId }: PanelPreviewHighProps) {
  if (!api.preview) return null;
  return (
    <div className="mt-3 p-4 rounded-xl bg-orange-500/10 border border-orange-500/40">
      <p className="text-xs uppercase tracking-widest text-orange-700 font-semibold mb-3">
        Preview de envío HIGH
      </p>
      <div className="grid gap-2 text-xs text-[color:var(--ink-2)]">
        <p>
          <span className="text-[color:var(--muted)]">Destino:</span>{" "}
          {api.preview.destino_short}
        </p>
        <p>
          <span className="text-[color:var(--muted)]">Costo estimado:</span>{" "}
          {api.preview.costo_creditos_estimado} créditos
        </p>
        <p>
          <span className="text-[color:var(--muted)]">Riesgo:</span> HIGH
        </p>
        <p className="whitespace-pre-wrap break-words">
          <span className="text-[color:var(--muted)]">Mensaje:</span>{" "}
          {api.preview.mensaje_preview}
        </p>
      </div>
      <label
        className="block text-xs text-[color:var(--muted)] mt-4 mb-2"
        htmlFor={`confirm-high-${accionId}`}
      >
        Escribe ENVIAR para confirmar
      </label>
      <input
        id={`confirm-high-${accionId}`}
        value={api.confirmacion}
        onChange={(ev) => api.setConfirmacion(ev.target.value)}
        className="w-full rounded-lg bg-[color:var(--surface)] border border-[color:var(--line)] px-3 py-2 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--muted)] outline-none focus:border-[color:var(--brand)]"
        autoComplete="off"
      />
      <div className="flex items-center justify-end gap-2 mt-3">
        <button
          onClick={api.cerrar}
          disabled={api.busy}
          className="btn-ghost px-4 py-2 rounded-full text-xs disabled:opacity-50"
        >
          Cancelar
        </button>
        <button
          onClick={api.confirmar}
          disabled={api.busy || api.confirmacion !== "ENVIAR"}
          className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
        >
          {api.busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
          Confirmar y enviar
        </button>
      </div>
    </div>
  );
}
