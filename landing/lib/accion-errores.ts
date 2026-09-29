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

/** Mensaje de éxito por operación · describe lo que realmente ocurrió. */
export const MENSAJE_EXITO: Record<"aprobar" | "rechazar" | "ejecutar", string> =
  {
    aprobar: "Acción aprobada. La lista se actualizó con su nuevo estado.",
    rechazar: "Acción rechazada. Ya está en el historial.",
    ejecutar: "Ejecución dry-run registrada. Revisa el resultado en el detalle.",
  };