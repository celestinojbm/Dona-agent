// Lista de aprobaciones pendientes con sus botones (J7.5).

import type { Aprobacion } from "@/lib/app-types";
import { decidirAprobacion } from "../acciones";
import FormAccion from "./form-accion";

const RIESGO: Record<string, string> = {
  LOW: "riesgo bajo",
  MEDIUM: "riesgo medio",
  HIGH: "riesgo alto",
  CRITICAL: "riesgo crítico",
};

export default function Aprobaciones({ items }: { items: Aprobacion[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-[color:var(--muted)]">No hay nada esperando tu decisión.</p>;
  }
  return (
    <ul className="space-y-4">
      {items.map((a) => (
        <li key={a.id} className="rounded-xl border border-[color:var(--line)] p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{a.operacion.replaceAll("_", " ")}</p>
            <span className="rounded-full border border-amber-300 px-2 py-0.5 text-xs text-amber-800 dark:text-amber-300">
              {RIESGO[a.riesgo] ?? a.riesgo}
            </span>
            {a.preview.simulado === true && (
              <span className="rounded-full border border-[color:var(--line)] px-2 py-0.5 text-xs text-[color:var(--muted)]">
                simulado
              </span>
            )}
          </div>
          {typeof a.preview.resumen === "string" && (
            <p className="mt-2 whitespace-pre-wrap text-sm text-[color:var(--ink-2)]">
              {a.preview.resumen}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-3">
            <FormAccion accion={decidirAprobacion} boton="Aprobar" className="contents">
              <input type="hidden" name="aprobacion_id" value={a.id} />
              <input type="hidden" name="decision" value="aprobar" />
            </FormAccion>
            <FormAccion accion={decidirAprobacion} boton="Rechazar" secundario className="contents">
              <input type="hidden" name="aprobacion_id" value={a.id} />
              <input type="hidden" name="decision" value="rechazar" />
            </FormAccion>
          </div>
        </li>
      ))}
    </ul>
  );
}
