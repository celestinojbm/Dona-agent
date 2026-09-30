// landing/lib/accion-errores.ts
//
// Traduce a texto accionable los errores que SÍ devuelven las rutas del
// Centro de acción (`app/api/automation/acciones/**`). No inventa
// códigos: solo cubre los que esas rutas emiten hoy.
//
//  400 invalid_accion_id · json_invalid · confirmacion_invalida
//      invalid_eventos_cursor · invalid_eventos_limite (GET /acciones/:id)
//  401 unauthenticated
//  403 no_subscription_in_session
//  404 accion_not_found
//  409 high_confirmation_not_available
//  502 backend_unavailable
//  504 backend_timeout

const MENSAJES_POR_CODIGO: Record<string, string> = {
  unauthenticated:
    "Tu sesión expiró. Vuelve a iniciar sesión para operar tus acciones.",
  no_subscription_in_session:
    "Tu sesión no tiene una suscripción asociada, así que no podemos operar esta acción.",
  invalid_accion_id: "El identificador de la acción no es válido.",
  invalid_eventos_cursor:
    "No pudimos pedir más eventos de esta acción. Vuelve a abrir el detalle.",
  invalid_eventos_limite:
    "No pudimos pedir más eventos de esta acción. Vuelve a abrir el detalle.",
  json_invalid: "La solicitud llegó mal formada. Intenta de nuevo.",
  confirmacion_invalida:
    "La confirmación no es válida: debe escribirse exactamente ENVIAR.",
  accion_not_found:
    "Esta acción ya no existe o no está asociada a tu negocio. Actualiza la lista.",
  high_confirmation_not_available:
    "La acción cambió de estado y ya no admite esta confirmación. Actualiza la lista y revisa su estado actual.",
  backend_unavailable:
    "El servicio de automatización no está disponible en este momento. Intenta de nuevo en unos minutos.",
  backend_timeout:
    "El servicio tardó demasiado en responder. Intenta de nuevo.",
};

const MENSAJE_POR_DEFECTO_5XX =
  "No pudimos completar la operación por un error del servidor. Intenta de nuevo.";
const MENSAJE_POR_DEFECTO_4XX =
  "No pudimos completar la operación con el estado actual de la acción.";

/** Resultado de una decisión · lo consumen la tarjeta y el panel. */
export interface ResultadoDecision {
  ok: boolean;
  mensaje: string;
  /**
   * true solo si el GET de la lista posterior a la decisión respondió
   * bien. Con false, lo que muestra la UI es un snapshot anterior y no
   * sirve para ofrecer otra decisión sobre la misma acción.
   */
  estadoActualizado: boolean;
}

function codigoDe(cuerpo: unknown): string | null {
  if (cuerpo && typeof cuerpo === "object" && "error" in cuerpo) {
    const error = (cuerpo as { error?: unknown }).error;
    if (typeof error === "string" && error) return error;
  }
  return null;
}

/**
 * Mensaje en español para mostrar al usuario a partir del status HTTP y
 * del cuerpo `{ error }` que devuelve la ruta.
 */
export function mensajeDeErrorAccion(status: number, cuerpo: unknown): string {
  const codigo = codigoDe(cuerpo);
  if (codigo && MENSAJES_POR_CODIGO[codigo]) return MENSAJES_POR_CODIGO[codigo];
  if (status >= 500) return MENSAJE_POR_DEFECTO_5XX;
  if (status >= 400) return MENSAJE_POR_DEFECTO_4XX;
  return MENSAJE_POR_DEFECTO_5XX;
}

export type OperacionDecision = "aprobar" | "rechazar" | "ejecutar" | "high";

/** Lo que el backend aceptó · no dice nada sobre el estado mostrado. */
export const MENSAJE_DECISION_REGISTRADA: Record<OperacionDecision, string> = {
  aprobar: "Acción aprobada.",
  rechazar: "Acción rechazada.",
  ejecutar: "Ejecución dry-run registrada.",
  high: "Confirmación HIGH registrada.",
};

// Solo se añade cuando la lista se recargó bien después de la decisión.
const MENSAJE_ESTADO_ACTUALIZADO: Record<OperacionDecision, string> = {
  aprobar: "La lista ya muestra su nuevo estado.",
  rechazar: "Ya está en el historial.",
  ejecutar: "Revisa el resultado en el detalle.",
  high: "La lista ya muestra su nuevo estado.",
};

export const MENSAJE_ESTADO_SIN_ACTUALIZAR =
  "No pudimos cargar su estado actualizado: actualiza antes de tomar otra decisión sobre esta acción.";

/** El POST no respondió · no sabemos si la decisión llegó al backend. */
export const MENSAJE_DECISION_INCIERTA =
  "Perdimos la conexión al enviar la decisión y no sabemos si se registró. Revisa el estado actual antes de intentarlo de nuevo.";

/**
 * Mensaje tras una decisión aceptada por el backend · separa "decisión
 * registrada" de "estado actualizado" para no afirmar que la lista se
 * refrescó cuando el GET posterior falló.
 */
export function mensajeDecision(
  op: OperacionDecision,
  estadoActualizado: boolean,
): string {
  const sufijo = estadoActualizado
    ? MENSAJE_ESTADO_ACTUALIZADO[op]
    : MENSAJE_ESTADO_SIN_ACTUALIZAR;
  return `${MENSAJE_DECISION_REGISTRADA[op]} ${sufijo}`;
}

/**
 * Mensaje tras una decisión tomada en el panel de detalle. Ahí el estado
 * se relee con la lectura canónica de la acción, no con la lista.
 */
export function mensajeDecisionPanel(
  op: OperacionDecision,
  estadoVerificado: boolean,
): string {
  const sufijo = estadoVerificado
    ? "El panel ya muestra su estado verificado."
    : MENSAJE_ESTADO_SIN_ACTUALIZAR;
  return `${MENSAJE_DECISION_REGISTRADA[op]} ${sufijo}`;
}

/** La re-lectura previa al envío falló: la decisión NO se envió. */
export const MENSAJE_NO_VERIFICADO_ANTES_DE_ENVIAR =
  "No pudimos verificar el estado actual de la acción justo antes de enviar, así que tu decisión no se envió. Actualiza el estado e intenta de nuevo.";

/** La re-lectura previa al envío mostró otro estado: la decisión NO se envió. */
export const MENSAJE_ESTADO_CAMBIO_ANTES_DE_ENVIAR =
  "La acción cambió mientras la revisabas, así que tu decisión no se envió. Revisa su estado actual antes de decidir.";

/**
 * El backend respondió 200 pero la lectura verificada no refleja la
 * decisión (p. ej. una transición que el backend ignoró).
 */
export function mensajeDecisionSinEfecto(etiquetaEstado: string): string {
  return `El servidor respondió, pero la acción sigue en «${etiquetaEstado}». Revisa su estado antes de decidir de nuevo.`;
}
