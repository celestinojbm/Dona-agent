// landing/lib/accion-formato.ts
//
// Helpers puros de presentación para el Centro de acción.
// Viven fuera del componente para poder probarlos sin DOM:
//   - formatearFechaHora  · ISO → texto en español, tolerante a null
//   - lineaTiempoAccion   · los timestamps reales que ya expone la API
//   - resumenResultado    · result_json → filas legibles
//
// Nada de esto inventa datos: si el backend no manda un timestamp o el
// result_json viene vacío, se muestra el vacío correspondiente.

import type { AccionAutomatizacion } from "./automation-types";

const FORMATO_FECHA_HORA = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * ISO → "28 sept 2026, 21:04". Devuelve "" si el valor es null, vacío o
 * no es una fecha válida · el llamador decide qué mostrar en ese caso.
 */
export function formatearFechaHora(iso: string | null | undefined): string {
  if (!iso) return "";
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "";
  return FORMATO_FECHA_HORA.format(fecha);
}

export interface HitoTiempo {
  clave: string;
  etiqueta: string;
  valor: string;
}

/**
 * Línea de tiempo real de la acción · solo con los timestamps que la API
 * ya devuelve. Cuando el backend agrega el audit log por acción, este
 * helper es el punto único a cambiar.
 */
export function lineaTiempoAccion(
  accion: Pick<
    AccionAutomatizacion,
    "created_at" | "approved_at" | "rejected_at" | "completed_at" | "updated_at"
  >,
): HitoTiempo[] {
  const candidatos: HitoTiempo[] = [
    {
      clave: "created_at",
      etiqueta: "Creada",
      valor: formatearFechaHora(accion.created_at),
    },
    {
      clave: "approved_at",
      etiqueta: "Aprobada",
      valor: formatearFechaHora(accion.approved_at),
    },
    {
      clave: "rejected_at",
      etiqueta: "Rechazada",
      valor: formatearFechaHora(accion.rejected_at),
    },
    {
      clave: "completed_at",
      etiqueta: "Completada",
      valor: formatearFechaHora(accion.completed_at),
    },
    {
      clave: "updated_at",
      etiqueta: "Última actualización",
      valor: formatearFechaHora(accion.updated_at),
    },
  ];
  return candidatos.filter((h) => h.valor !== "");
}

export interface FilaResultado {
  clave: string;
  valor: string;
}

export interface ResumenResultado {
  vacio: boolean;
  filas: FilaResultado[];
  /** JSON indentado · escape para claves anidadas o payload no parseable. */
  crudo: string | null;
}

function valorLegible(valor: unknown): string {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "string") return valor || "—";
  if (typeof valor === "number" || typeof valor === "boolean") {
    return String(valor);
  }
  try {
    return JSON.stringify(valor);
  } catch {
    return String(valor);
  }
}

/**
 * `result_json` → filas clave/valor de primer nivel. Los valores
 * anidados se muestran como JSON compacto porque el backend puede
 * devolver estructuras (no las aplana la UI para no inventar semántica).
 */
export function resumenResultado(resultJson: string | null | undefined): ResumenResultado {
  if (!resultJson || !resultJson.trim()) {
    return { vacio: true, filas: [], crudo: null };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(resultJson);
  } catch {
    return { vacio: false, filas: [], crudo: resultJson };
  }
  if (parsed === null || typeof parsed !== "object") {
    return { vacio: false, filas: [], crudo: JSON.stringify(parsed, null, 2) };
  }
  const entradas = Object.entries(parsed as Record<string, unknown>);
  if (entradas.length === 0) {
    return { vacio: true, filas: [], crudo: null };
  }
  return {
    vacio: false,
    filas: entradas.map(([clave, valor]) => ({
      clave,
      valor: valorLegible(valor),
    })),
    crudo: JSON.stringify(parsed, null, 2),
  };
}
