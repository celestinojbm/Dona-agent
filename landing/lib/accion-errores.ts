// landing/lib/accion-errores.ts
//
// Traduce a texto accionable los errores que SÍ devuelven las rutas del
// Centro de acción (`app/api/automation/acciones/**`). No inventa
// códigos: solo cubre los que esas rutas emiten hoy.
//
//  400 invalid_accion_id · json_invalid · confirmacion_invalida
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
