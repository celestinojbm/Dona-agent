// landing/lib/automation-types.ts — Tipos compartidos T2.1.B
//
// Estos tipos los usan tanto el bridge (server-only) como los componentes
// del dashboard (client). Por eso viven aparte de internal-bridge.ts.

export type EstadoAccion =
  | "pending"
  | "needs_approval"
  | "approved"
  | "running"
  | "completed"
  | "rejected"
  | "failed"
  | "cancelled";

export type NivelRiesgo = "low" | "medium" | "high" | "critical";

/**
 * Contrato explícito que la API expone para que la UI sepa qué control
 * debe operar sobre la acción ahora · evita reimplementar la matriz
 * (estado × riesgo) en cada cliente. Mantiene paridad con
 * `agent.automation.permissions.NextRequiredAction`.
 *
 *   execute_available               · listo para ejecutarse por el control
 *                                     genérico del Action Center.
 *   approval_required               · espera aprobación humana simple.
 *   dedicated_confirmation_required · aprobado pero requiere UX dedicada
 *                                     con preview/costo/riesgo (HIGH approved).
 *   reinforced_approval_required    · CRITICAL · bloqueado · necesita
 *                                     confirmación reforzada (futura).
 *   none                            · terminal o en ejecución · no ofrecer
 *                                     siguiente control sobre la acción.
 */
export type NextRequiredAction =
  | "execute_available"
  | "approval_required"
  | "dedicated_confirmation_required"
  | "reinforced_approval_required"
  | "none";

/** Acción tal como la devuelve el backend (campos sanitizados). */
export interface AccionAutomatizacion {
  id: number;
  opportunity_id: string;
  playbook_id: string;
  tipo_accion: string;
  titulo: string;
  descripcion: string;
  razon_recomendacion: string;
  estado: EstadoAccion;
  riesgo: NivelRiesgo;
  costo_creditos_estimado: number;
  requires_approval: boolean;
  /** JSON serializado · output del ejecutor dry-run */
  result_json: string;
  /** Sanitizado · max 500 chars */
  error_message: string;
  created_at: string | null;
  updated_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  completed_at: string | null;
  /**
   * Siguiente control que debe operar la acción · contrato explícito
   * del backend. Opcional para compat con payloads previos al contrato;
   * la UI cae a un cálculo local sobre (estado, riesgo) si no llega.
   */
  next_required_action?: NextRequiredAction;
  /**
   * Motivo corto por el que la acción no es ejecutable por el control
   * genérico (texto plano en español, ya sanitizado por el backend).
   * Vacío cuando no aplica.
   */
  execution_block_reason?: string;
}

export interface OportunidadDetectada {
  id: string;
  tipo: string;
  titulo: string;
  descripcion: string;
  razon: string;
  prioridad: number;
  impacto_estimado: "alto" | "medio" | "bajo";
  riesgo: NivelRiesgo;
  fuente_datos: string[];
  playbook_sugerido: string;
}

export interface AccionesResponse {
  acciones: AccionAutomatizacion[];
  count: number;
}

export interface OportunidadesResponse {
  oportunidades: OportunidadDetectada[];
  count: number;
}

export type PerfilEstado = "missing" | "incomplete" | "ready";

export interface PerfilEstadoInfo {
  perfil_estado?: PerfilEstado;
  perfil_campos_llenos?: number;
  perfil_campos_totales?: number;
  perfil_razon?: string;
  perfil_siguiente_paso?: string;
}

export interface GenerarResponse extends PerfilEstadoInfo {
  oportunidades_evaluadas: number;
  acciones: AccionAutomatizacion[];
}

export interface OportunidadesConEstadoResponse extends PerfilEstadoInfo {
  oportunidades: OportunidadDetectada[];
  count: number;
}

export interface EjecutarResponse {
  accion: AccionAutomatizacion;
  ejecucion: {
    estado_final: EstadoAccion;
    result?: Record<string, unknown>;
    error?: string;
  };
}

export interface HighPreviewResponse {
  ok: boolean;
  accion_id: number;
  tipo_accion: "enviar_mensaje_whatsapp";
  titulo: string;
  descripcion: string;
  riesgo: "high";
  estado: EstadoAccion;
  costo_creditos_estimado: number;
  destino_short: string;
  numero_destino: string;
  mensaje_preview: string;
  longitud_mensaje: number;
  confirmacion_requerida: "ENVIAR";
}

export interface AccionApiResult<T> {
  ok: boolean;
  status?: number;
  data?: T;
  error?: string;
}
