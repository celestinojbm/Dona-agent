// landing/app/api/chat/route.ts
//
// POST · procesa un turno de chat web con paridad total con WhatsApp.
// El usuario escribe desde el dashboard; este route reenvía el mensaje al
// backend (/internal/chat), que lo procesa con LA MISMA función que WhatsApp
// (generar_respuesta) preservando todos los gates (cobro, TCPA, preparar/
// confirmar). Devuelve el texto de Dona para mostrarlo en la UI.
//
// Seguridad:
//   - subscription_id viene SIEMPRE de auth() server-side (T1.4.D guardrail).
//     NUNCA aceptamos telefono ni subscription_id del cliente.
//   - El body del cliente sólo aporta el texto del mensaje.
//
// A diferencia de /api/assets y /api/reportes (GET read-only con fallback a
// empty state), aquí un fallo del backend SÍ es un error observable: el usuario
// espera respuesta. No hay "empty state" que devolver, así que mapeamos los
// errores a status HTTP claros que la UI muestra sin exponer secrets ni PII.
//
// maxDuration: el turno puede tardar hasta ~120s (LLM + tools). Subimos el
// límite de esta función serverless SÓLO para esta ruta.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { enviarMensajeChat } from "@/lib/chat-bridge";

// Vercel/Next: permite que esta función corra hasta 120s (el chat espera al
// LLM). Otras rutas conservan su default. El plan de hosting debe permitirlo;
// si no, el techo real lo impone la plataforma.
export const maxDuration = 120;

// Tope defensivo del tamaño del mensaje del lado del route · el backend tiene
// su propio cap, este evita reenviar payloads absurdos.
const CHAT_MAX_LONGITUD = 8000;

export async function POST(req: Request) {
  const session = await auth();
  if (!session) {
    console.warn("[CHAT] POST · missing_session");
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) {
    // JWT antiguo sin subscriptionId · el chat necesita una sub resuelta.
    console.warn("[CHAT] POST · missing_subscription_id");
    return NextResponse.json({ error: "subscription_required" }, { status: 400 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "json_invalido" }, { status: 400 });
  }
  const mensajeRaw = (body as { mensaje?: unknown })?.mensaje;
  if (typeof mensajeRaw !== "string" || !mensajeRaw.trim()) {
    return NextResponse.json({ error: "mensaje_vacio" }, { status: 400 });
  }
  const mensaje = mensajeRaw.trim().slice(0, CHAT_MAX_LONGITUD);

  const result = await enviarMensajeChat(subscriptionId, mensaje);
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }

  // Error categorizado · log seguro (sin secrets, sin telefono, sin el mensaje)
  if (result.status === 404) {
    console.warn("[CHAT] POST · backend_404 subscription_no_persistida");
    return NextResponse.json({ error: "subscription_not_found" }, { status: 404 });
  }
  if (result.status === 429) {
    console.warn("[CHAT] POST · backend_429 rate_limit");
    return NextResponse.json({ error: "rate_limit" }, { status: 429 });
  }
  if (result.status === 401) {
    console.error(
      "[CHAT] POST · backend_401 INTERNAL_BRIDGE_SECRET desincronizado entre Vercel/Render?",
    );
    return NextResponse.json({ error: "backend_auth_error" }, { status: 502 });
  }
  if (result.error === "timeout") {
    console.error("[CHAT] POST · bridge_timeout");
    return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
  }
  if (result.error === "backend_url_missing") {
    console.error("[CHAT] POST · missing_env BACKEND_URL");
  } else if (result.error === "internal_bridge_secret_missing") {
    console.error("[CHAT] POST · missing_env INTERNAL_BRIDGE_SECRET");
  } else {
    console.error(
      `[CHAT] POST · backend_${result.status ?? "unknown"} ${result.error ?? ""}`,
    );
  }
  return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
}
