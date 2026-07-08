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
//   - El body del cliente sólo aporta texto y, opcionalmente, media (voz/imagen
//     en base64). Se valida formato y tamaño (caps) antes de reenviar; cualquier
//     subscription_id/telefono en el body se ignora por completo.
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
import type { ChatMediaWire } from "@/lib/chat-types";

// Vercel/Next: permite que esta función corra hasta 120s (el chat espera al
// LLM). Otras rutas conservan su default. El plan de hosting debe permitirlo;
// si no, el techo real lo impone la plataforma.
export const maxDuration = 120;

// Tope defensivo del tamaño del mensaje del lado del route · el backend tiene
// su propio cap, este evita reenviar payloads absurdos.
const CHAT_MAX_LONGITUD = 8000;

// Cap por adjunto (audio/imagen), decodificado · MISMO valor que el backend
// (_CHAT_MAX_MEDIA_BYTES). Este es el primer cinturón: rechaza antes de firmar
// y reenviar un payload gigante. El cliente ya reduce imágenes, pero un turno
// puede llegar por otras vías.
const CHAT_MAX_MEDIA_BYTES = 12 * 1024 * 1024; // 12 MB
// Tope del caption de imagen · evita reenviar texto desmesurado pegado a la foto.
const CHAT_MAX_CAPTION = 2000;

// base64 canónico SIN saltos de línea ni prefijo `data:` (el cliente ya lo
// quita). La validación estricta evita reenviar basura al backend.
const BASE64_RE = /^[A-Za-z0-9+/]+={0,2}$/;

/** Bytes decodificados de un base64 canónico (sin allocar el Buffer). */
function base64ByteLength(b64: string): number {
  const len = b64.length;
  const padding = b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0;
  return Math.floor((len * 3) / 4) - padding;
}

type AdjuntoValidado =
  | { ok: true; b64: string }
  | { ok: false; error: string; status: number };

/**
 * Valida un base64 de adjunto. Devuelve null si no venía adjunto (campo
 * ausente/no-string), o el resultado tipado si venía. Rechaza formato inválido
 * (400) y tamaño excedido (413), igual que el backend, pero sin round-trip.
 */
function validarAdjunto(valor: unknown): AdjuntoValidado | null {
  if (typeof valor !== "string" || valor.length === 0) return null;
  if (valor.length % 4 !== 0 || !BASE64_RE.test(valor)) {
    return { ok: false, error: "adjunto_invalido", status: 400 };
  }
  if (base64ByteLength(valor) > CHAT_MAX_MEDIA_BYTES) {
    return { ok: false, error: "adjunto_demasiado_grande", status: 413 };
  }
  return { ok: true, b64: valor };
}

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
  const b = (body ?? {}) as Record<string, unknown>;

  // Texto: opcional ahora (puede venir sólo un adjunto). Se normaliza y trunca.
  const mensajeRaw = b.mensaje;
  const mensaje =
    typeof mensajeRaw === "string"
      ? mensajeRaw.trim().slice(0, CHAT_MAX_LONGITUD)
      : "";

  // Media (voz/imagen). subscription_id NUNCA sale del cliente: lo pone el
  // bridge desde la sesión (server-side). El cliente sólo aporta texto y media.
  const media: ChatMediaWire = {};

  const audio = validarAdjunto(b.audio_base64);
  if (audio && !audio.ok) {
    return NextResponse.json({ error: audio.error }, { status: audio.status });
  }
  if (audio?.ok) {
    media.audio_base64 = audio.b64;
    if (typeof b.audio_mime === "string" && b.audio_mime.startsWith("audio/")) {
      media.audio_mime = b.audio_mime;
    }
  }

  const imagen = validarAdjunto(b.imagen_base64);
  if (imagen && !imagen.ok) {
    return NextResponse.json({ error: imagen.error }, { status: imagen.status });
  }
  if (imagen?.ok) {
    media.imagen_base64 = imagen.b64;
    if (typeof b.imagen_mime === "string" && b.imagen_mime.startsWith("image/")) {
      media.imagen_mime = b.imagen_mime;
    }
    if (typeof b.imagen_caption === "string" && b.imagen_caption.trim()) {
      media.imagen_caption = b.imagen_caption.trim().slice(0, CHAT_MAX_CAPTION);
    }
  }

  const hayMedia = Boolean(media.audio_base64 || media.imagen_base64);
  if (!mensaje && !hayMedia) {
    return NextResponse.json({ error: "mensaje_vacio" }, { status: 400 });
  }

  const result = await enviarMensajeChat(
    subscriptionId,
    mensaje,
    hayMedia ? media : undefined,
  );
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
  if (result.status === 413) {
    // El backend rechazó un adjunto por tamaño (segundo cinturón tras el cap
    // del route). Mensaje específico para que la UI lo explique.
    console.warn("[CHAT] POST · backend_413 adjunto_demasiado_grande");
    return NextResponse.json(
      { error: "adjunto_demasiado_grande" },
      { status: 413 },
    );
  }
  if (result.status === 400) {
    // 400 del backend tras validar aquí ⇒ base64 inválido según su criterio
    // estricto. La UI lo trata como adjunto ilegible.
    console.warn("[CHAT] POST · backend_400 adjunto_invalido");
    return NextResponse.json({ error: "adjunto_invalido" }, { status: 400 });
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
