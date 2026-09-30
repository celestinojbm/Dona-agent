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

const FORMATO_FECHA_HORA_SEGUNDOS = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

// El backend escribe todos los timestamps con datetime.utcnow() y los
// serializa sin zona ("2026-05-09T00:00:00"). `new Date` leería esa forma
// como hora LOCAL del navegador y la desplazaría; se marca como UTC.
const ISO_SIN_ZONA = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

function parsearIsoUtc(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const fecha = new Date(ISO_SIN_ZONA.test(iso) ? `${iso}Z` : iso);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

/**
 * ISO → "28 sept 2026, 21:04" en la hora local del navegador. Devuelve ""
 * si el valor es null, vacío o no es una fecha válida · el llamador decide
 * qué mostrar en ese caso. Un ISO sin zona se interpreta como UTC.
 */
export function formatearFechaHora(iso: string | null | undefined): string {
  const fecha = parsearIsoUtc(iso);
  return fecha ? FORMATO_FECHA_HORA.format(fecha) : "";
}

/** Igual que formatearFechaHora pero con segundos · para "verificado a las". */
export function formatearFechaHoraSegundos(iso: string | null | undefined): string {
  const fecha = parsearIsoUtc(iso);
  return fecha ? FORMATO_FECHA_HORA_SEGUNDOS.format(fecha) : "";
}

// Nombres legibles de los eventos de la bitácora
// (agent/automation/audit.py:EVENTOS_VALIDOS) que pueden llevar accion_id.
const ETIQUETA_EVENTO: Record<string, string> = {
  action_created: "Acción creada",
  action_approved: "Acción aprobada",
  action_rejected: "Acción rechazada",
  action_cancelled: "Acción cancelada",
  action_started: "Ejecución iniciada",
  action_completed: "Acción completada",
  action_failed: "La acción falló",
  action_blocked_critical: "Bloqueada por riesgo crítico",
  action_blocked_insufficient_credits: "Bloqueada por créditos insuficientes",
  credits_reserved: "Créditos reservados",
  credits_confirmed: "Cobro de créditos confirmado",
  credits_released: "Créditos devueltos",
  credits_reservation_failed: "No se pudo reservar créditos",
  credits_reservation_reconciled: "Reserva de créditos conciliada",
  high_preview_requested: "Preview HIGH solicitado",
  high_preview_rendered: "Preview HIGH mostrado",
  high_confirmation_submitted: "Confirmación HIGH enviada",
  high_confirmation_rejected: "Confirmación HIGH rechazada",
  high_execution_claimed: "Envío HIGH en curso",
  high_execution_succeeded: "Envío HIGH completado",
  high_execution_failed: "Envío HIGH fallido",
  high_execution_duplicate_blocked: "Envío HIGH duplicado bloqueado",
  high_consent_registered: "Consentimiento del destino registrado",
  high_send_blocked_policy: "Envío bloqueado por política de terceros",
  mission_recover_lead_action_linked: "Enlazada a una misión",
  mission_recover_lead_completed: "Misión completada",
  mission_recover_lead_reconciled: "Misión conciliada",
  email_action_prepared: "Correo preparado",
  email_action_rerendered: "Correo actualizado",
  email_action_superseded: "Correo reemplazado por otro",
  email_confirmation_hold: "Confirmación de correo en espera",
  email_confirmation_rejected: "Confirmación de correo rechazada",
  email_action_cancelled: "Correo cancelado",
  email_action_expired: "Correo expirado",
  email_payload_corrupted: "Contenido del correo inválido",
};

/**
 * Nombre legible de un evento de la bitácora. Un tipo desconocido no se
 * disfraza: se muestra como "Evento registrado" y el llamador enseña el
 * código tal cual.
 */
export function etiquetaEvento(evento: string): { texto: string; conocido: boolean } {
  const texto = ETIQUETA_EVENTO[evento];
  return texto
    ? { texto, conocido: true }
    : { texto: "Evento registrado", conocido: false };
}

export interface HitoTiempo {
  clave: string;
  etiqueta: string;
  valor: string;
}

/**
 * Marcas de tiempo que trae la propia fila de la acción. Los pasos
 * intermedios comprobados salen de la bitácora (`eventos` de la lectura
 * canónica), no de aquí.
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
