// Chip de estado de tarea (J7.5).

import { etiquetaEstado } from "@/lib/app-types";

const TONO: Record<string, string> = {
  completada: "border-emerald-300 text-emerald-800 dark:text-emerald-300",
  necesita_aprobacion: "border-amber-300 text-amber-800 dark:text-amber-300",
  bloqueada: "border-amber-300 text-amber-800 dark:text-amber-300",
  fallida: "border-rose-300 text-rose-700 dark:text-rose-300",
  en_ejecucion: "border-indigo-300 text-indigo-700 dark:text-indigo-300",
};

export default function EstadoTarea({ estado }: { estado: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        TONO[estado] ?? "border-[color:var(--line)] text-[color:var(--ink-2)]"
      }`}
    >
      {etiquetaEstado(estado)}
    </span>
  );
}
