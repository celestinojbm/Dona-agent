// landing/lib/internal-bridge.ts
// Bridge landing → backend para reenviar eventos Stripe verificados (T1.3.E).
//
// Stripe Dashboard apunta a este landing (Vercel). El handler /api/webhook
// verifica la firma de Stripe; si pasa, llama a este módulo para reenviar el
// evento al backend (Render) firmado con HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET).
// El backend valida el HMAC en /internal/stripe-event y procesa el evento
// (acreditación de créditos, etc.).
//
// Importante: el cuerpo que se firma DEBE ser exactamente el cuerpo que se
// envía al backend. Por eso construimos el JSON una sola vez y reusamos el
// string para HMAC y para el body del fetch.

import crypto from "node:crypto";

export type BridgeResult = {
  ok: boolean;
  /** Status devuelto por el backend; undefined si el fetch nunca completó. */
  status?: number;
  /** Mensaje de error opaco (no contiene secrets). */
  error?: string;
};

const BRIDGE_TIMEOUT_MS = 8000; // < 10s timeout de Stripe

/**
 * Reenvia un evento Stripe verificado al backend Dona.
 *
 * Reglas (T1.3.E):
 * - Si BACKEND_URL o INTERNAL_BRIDGE_SECRET faltan → ok=false (caller
 *   debe responder 500 a Stripe para que reintente).
 * - Si el backend responde 2xx → ok=true.
 * - Si el backend responde no-2xx (incluido 401/400) → ok=false. El caller
 *   debe responder 500 a Stripe (mejor retry + alerta que perder evento).
 * - Si el fetch tira (DNS, timeout, red) → ok=false.
 *
 * No filtra el secret en logs.
 */
export async function reenviarEventoStripeABackend(
  evento: unknown,
): Promise<BridgeResult> {
  const backendUrl = process.env.BACKEND_URL?.trim();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();

  if (!backendUrl) {
    console.error("[BRIDGE] BACKEND_URL no configurada — no se reenvía evento");
    return { ok: false, error: "backend_url_missing" };
  }
  if (!secret) {
    console.error(
      "[BRIDGE] INTERNAL_BRIDGE_SECRET no configurada — no se reenvía evento",
    );
    return { ok: false, error: "internal_bridge_secret_missing" };
  }

  // El body que firmamos es el body exacto que enviamos. JSON.stringify es
  // determinista para el resultado de constructEvent (que es un objeto
  // simple sin getters); diferentes llamadas producen el mismo string.
  const body = JSON.stringify(evento);

  const signature = crypto
    .createHmac("sha256", secret)
    .update(body, "utf8")
    .digest("hex");

  const url = `${backendUrl.replace(/\/+$/, "")}/internal/stripe-event`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BRIDGE_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Signature": signature,
      },
      body,
      signal: controller.signal,
    });

    if (res.ok) {
      return { ok: true, status: res.status };
    }

    // Backend respondió no-2xx. Loguear status + body truncado, sin filtrar
    // headers ni secrets.
    let preview = "";
    try {
      const txt = await res.text();
      preview = txt.slice(0, 500);
    } catch {
      // ignorar errores leyendo el body de error
    }
    console.error(
      `[BRIDGE] Backend respondió ${res.status} ${res.statusText} — body: ${preview}`,
    );
    return { ok: false, status: res.status, error: `backend_${res.status}` };
  } catch (err) {
    const isAbort =
      err instanceof Error &&
      (err.name === "AbortError" || err.message.includes("aborted"));
    if (isAbort) {
      console.error(
        `[BRIDGE] Timeout (${BRIDGE_TIMEOUT_MS}ms) llamando al backend`,
      );
      return { ok: false, error: "timeout" };
    }
    // Otros errores: red, DNS, etc. No incluimos err entero por si Node
    // adjunta info sensible.
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE] Fetch al backend falló: ${msg}`);
    return { ok: false, error: "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}
