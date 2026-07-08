// landing/lib/chat-bridge.ts — Bridge HMAC para el Chat web (Fase 1)
//
// Mismo patrón que reportes-bridge.ts / assets-bridge.ts · firma con
// HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET) y llama /internal/chat en el
// backend Render.
//
// DIFERENCIA CLAVE con los otros bridges — el TIMEOUT:
//   Los bridges de lectura (reportes/assets) usan ~8s porque el backend sólo
//   hace SELECTs. El chat, en cambio, llama a generar_respuesta (LLM + loop de
//   tools), que tarda 10-30s y puede acercarse a los 90s en el peor caso. Un
//   timeout de 8s abortaría SIEMPRE la respuesta. Por eso este bridge usa
//   ~120s, holgado sobre el timeout de 90s que aplica el backend en
//   /internal/chat. Este timeout largo es EXCLUSIVO de la ruta de chat; no se
//   toca el timeout global de los demás bridges.
//
// Primera versión NO-streaming: el landing muestra "escribiendo…" mientras
// espera este fetch. Streaming SSE queda como follow-up.
//
// Reglas de seguridad:
//   - subscription_id viene SIEMPRE de auth() server-side (T1.4.D).
//   - INTERNAL_BRIDGE_SECRET nunca llega al cliente.
//   - El backend resuelve telefono desde subscription_id y procesa el mensaje
//     SÓLO sobre ese telefono (anti-IDOR). El cliente NUNCA manda telefono.

import "server-only";

import crypto from "node:crypto";

import type { ChatApiResult, ChatMediaWire, ChatResponse } from "./chat-types";

// 120s · holgado sobre el timeout de 90s del backend en /internal/chat.
const CHAT_BRIDGE_TIMEOUT_MS = 120_000;

function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function generarRequestId(): string {
  return "lnd_" + crypto.randomBytes(6).toString("hex");
}

/**
 * Envía un turno de chat del usuario al backend y devuelve la respuesta de Dona.
 *
 * - Firma el body JSON con HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET).
 * - Lee BACKEND_URL e INTERNAL_BRIDGE_SECRET de env; nunca los expone al
 *   resultado.
 * - Propaga `status` para que el route handler mapee 404/401/429/413/timeout.
 * - Logs no incluyen subscription_id completo ni el texto del mensaje (PII).
 *
 * Media (Fase 3): además del texto, un turno puede traer voz y/o imagen en
 * `media` (base64 SIN prefijo). Se exige ≥1 de: `mensaje`, `media.audio_base64`
 * o `media.imagen_base64`. Los campos de media SÓLO se agregan al body cuando
 * están presentes, así un turno de sólo-texto sigue firmando y enviando
 * EXACTAMENTE `{subscription_id, mensaje}` (sin ruido para el backend).
 *
 * Llamar SÓLO desde código server-side (route handlers), nunca desde el
 * cliente: imprime el secret en el HMAC.
 */
export async function enviarMensajeChat(
  subscriptionId: string,
  mensaje: string,
  media?: ChatMediaWire,
): Promise<ChatApiResult> {
  const backendUrl = process.env.BACKEND_URL?.trim();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();

  const texto = mensaje?.trim() ?? "";
  const hayMedia = Boolean(media?.audio_base64 || media?.imagen_base64);

  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  // Debe venir texto o al menos un adjunto. Sólo-texto vacío y sin media es un
  // turno vacío (mismo criterio que el backend: missing_mensaje).
  if (!texto && !hayMedia) return { ok: false, error: "missing_mensaje" };
  if (!backendUrl) {
    console.error("[BRIDGE-CHAT] BACKEND_URL no configurada");
    return { ok: false, error: "backend_url_missing" };
  }
  if (!secret) {
    console.error("[BRIDGE-CHAT] INTERNAL_BRIDGE_SECRET no configurada");
    return { ok: false, error: "internal_bridge_secret_missing" };
  }

  // El body que firmamos es exactamente el body que enviamos. NUNCA incluye
  // telefono: el backend lo resuelve desde subscription_id (anti-IDOR). Los
  // campos de media se añaden SÓLO si vienen, para no alterar el body de
  // sólo-texto.
  const body: Record<string, string> = { subscription_id: subscriptionId };
  if (texto) body.mensaje = texto;
  if (media?.audio_base64) {
    body.audio_base64 = media.audio_base64;
    if (media.audio_mime) body.audio_mime = media.audio_mime;
  }
  if (media?.imagen_base64) {
    body.imagen_base64 = media.imagen_base64;
    if (media.imagen_mime) body.imagen_mime = media.imagen_mime;
    if (media.imagen_caption) body.imagen_caption = media.imagen_caption;
  }
  const bodyStr = JSON.stringify(body);
  const signature = crypto
    .createHmac("sha256", secret)
    .update(bodyStr, "utf8")
    .digest("hex");

  const url = `${backendUrl.replace(/\/+$/, "")}/internal/chat`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), CHAT_BRIDGE_TIMEOUT_MS);
  const reqId = generarRequestId();
  const subShort = shortId(subscriptionId);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Signature": signature,
        "X-Request-ID": reqId,
      },
      body: bodyStr,
      signal: controller.signal,
    });

    if (res.ok) {
      const data = (await res.json()) as ChatResponse;
      return { ok: true, data };
    }

    console.error(
      `[BRIDGE-CHAT] rid=${reqId} status=${res.status} sub=${subShort}`,
    );
    return { ok: false, status: res.status, error: `backend_${res.status}` };
  } catch (err) {
    const isAbort =
      err instanceof Error &&
      (err.name === "AbortError" || err.message.includes("aborted"));
    if (isAbort) {
      console.error(
        `[BRIDGE-CHAT] rid=${reqId} timeout (${CHAT_BRIDGE_TIMEOUT_MS}ms) sub=${subShort}`,
      );
      return { ok: false, error: "timeout" };
    }
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE-CHAT] rid=${reqId} fetch falló: ${msg}`);
    return { ok: false, error: "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}
