// landing/lib/accion-decision.ts
//
// Reglas de presentación y decisión del Centro de acción · extraídas del
// componente para que la tarjeta de la lista y el panel de detalle usen
// exactamente la misma matriz (estado × riesgo) y el mismo copy.
//
// El contrato lo sigue mandando el backend (`next_required_action` +
// `execution_block_reason`); el cálculo local solo cubre payloads legacy.

import type {
  AccionAutomatizacion,
  EstadoAccion,
  NextRequiredAction,
  NivelRiesgo,
} from "./automation-types";

export const RIESGO_LABEL: Record<NivelRiesgo, string> = {
  low: "Bajo",
  medium: "Medio",
  high: "Alto",
  critical: "Crítico",
};

export const RIESGO_COLOR: Record<NivelRiesgo, string> = {
  low: "bg-emerald-600/10 text-emerald-700 border-emerald-600/40",
  medium: "bg-amber-500/15 text-amber-700 border-amber-500/40",
  high: "bg-orange-500/10 text-orange-700 border-orange-500/40",
  critical: "bg-[#e64263]/10 text-[#e64263] border-[#e64263]/40",
};

export const ESTADO_LABEL: Record<EstadoAccion, string> = {
  pending: "Lista para ejecutar",
  needs_approval: "Esperando tu aprobación",
  approved: "Aprobada · lista para ejecutar",
  running: "Ejecutando…",
  completed: "Completada",
  rejected: "Rechazada",
  failed: "Falló",
  cancelled: "Cancelada",
};

export const ESTADO_COLOR: Record<EstadoAccion, string> = {
  pending: "text-emerald-700",
  needs_approval: "text-amber-700",
  approved: "text-sky-700",
  running: "text-sky-700",
  completed: "text-emerald-700",
  rejected: "text-[color:var(--muted)]",
  failed: "text-[color:var(--dato-neg)]",
  cancelled: "text-[color:var(--muted)]",
};

// Copy local por defecto cuando el backend NO envía
// execution_block_reason (payloads legacy previos al contrato). Mantiene
// la UX anterior intacta para clientes que aún no leen el contrato.
export const COPY_HIGH_APROBADA_FALLBACK =
  "Esta acción es de alto impacto. Está aprobada, pero necesita " +
  "confirmación dedicada antes de ejecutar un efecto externo real.";
export const COPY_CRITICAL_FALLBACK =
  "Esta acción es crítica. Requiere confirmación reforzada y aún no " +
  "puede ejecutarse automáticamente.";

export function esTerminal(estado: EstadoAccion): boolean {
  return ["completed", "rejected", "failed", "cancelled"].includes(estado);
}

export function esActiva(estado: EstadoAccion): boolean {
  return !esTerminal(estado);
}

// Fallback local que reimplementa el mismo contrato de
// `agent.automation.permissions.calcular_next_required_action`. Solo se
// usa cuando el payload viene sin el contrato (acciones serializadas por
// versiones previas del backend). Mientras backend mande
// next_required_action, este helper no se ejecuta.
export function calcularNextRequiredActionLocal(
  estado: EstadoAccion,
  riesgo: NivelRiesgo,
): { next: NextRequiredAction; motivo: string } {
  if (
    estado === "completed" ||
    estado === "rejected" ||
    estado === "failed" ||
    estado === "cancelled" ||
    estado === "running"
  ) {
    return { next: "none", motivo: "" };
  }
  if (riesgo === "critical") {
    return { next: "reinforced_approval_required", motivo: COPY_CRITICAL_FALLBACK };
  }
  if (riesgo === "high") {
    if (estado === "approved") {
      return {
        next: "dedicated_confirmation_required",
        motivo: COPY_HIGH_APROBADA_FALLBACK,
      };
    }
    if (estado === "needs_approval") {
      return { next: "approval_required", motivo: "" };
    }
    return { next: "none", motivo: "" };
  }
  // low / medium · cada riesgo abre ejecución solo si su estado lo
  // justifica. LOW puede auto-ejecutar desde pending; MEDIUM exige
  // aprobación humana primero · pending/medium aquí solo ocurre por
  // datos legacy o un bug, y NO se debe ofrecer ningún control genérico
  // (TRANSICIONES backend sólo permite pending → running/cancelled/
  // rejected, así que aprobar desde pending sería transición inválida).
  if (estado === "needs_approval") {
    return { next: "approval_required", motivo: "" };
  }
  if (riesgo === "low" && (estado === "pending" || estado === "approved")) {
    return { next: "execute_available", motivo: "" };
  }
  if (riesgo === "medium" && estado === "approved") {
    return { next: "execute_available", motivo: "" };
  }
  return { next: "none", motivo: "" };
}

export function resolverNextRequiredAction(
  accion: AccionAutomatizacion,
): { next: NextRequiredAction; motivo: string } {
  const fromApi = accion.next_required_action;
  if (fromApi) {
    return {
      next: fromApi,
      motivo: accion.execution_block_reason ?? "",
    };
  }
  return calcularNextRequiredActionLocal(accion.estado, accion.riesgo);
}

/**
 * Etiqueta de estado a mostrar · una HIGH aprobada no está "lista para
 * ejecutar": queda pendiente de la confirmación dedicada, y el texto
 * debe reflejarlo para no confundirse con las LOW/MEDIUM ejecutables.
 */
export function etiquetaEstadoMostrado(
  estado: EstadoAccion,
  nextRequired: NextRequiredAction,
): string {
  if (nextRequired === "dedicated_confirmation_required") {
    return "Aprobada · requiere confirmación dedicada";
  }
  return ESTADO_LABEL[estado];
}
