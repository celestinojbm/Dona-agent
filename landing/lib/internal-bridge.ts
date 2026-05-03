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
//
// `server-only` evita que cualquier Client Component o código de cliente lo
// importe accidentalmente: si pasa, el build de Next falla con un error
// claro. Estas funciones leen INTERNAL_BRIDGE_SECRET y nunca deben correr
// en el browser.
import "server-only";

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


// ── T1.4.D: lectura del resumen de usuario para el dashboard ──────────────
//
// El backend expone POST /internal/usuario-resumen (T1.4.C) que devuelve el
// dato consolidado para el dashboard. Esta función firma con HMAC y traduce
// la respuesta a tipos TS para que el route handler pueda mergear con Stripe.

/** Forma de la transacción tal como la devuelve el backend. */
export type TransaccionResumen = {
  delta: number;
  razon: string;
  saldo_resultante: number;
  creado: string | null;
};

/** Estructura completa del response 200 de /internal/usuario-resumen. */
export type UsuarioResumen = {
  usuario: {
    id: string;
    email: string | null;
    telefono: string;
  };
  creditos: {
    saldo_actual: number;
    creditos_mensuales: number;
    ultimo_movimiento: TransaccionResumen | null;
  };
  suscripcion: {
    estado: string;
    plan: string;
    stripe_customer_id: string;
    stripe_subscription_id: string;
    current_period_end: number | null;
    cancel_at_period_end: boolean;
    actualizado: string | null;
  };
  transacciones_recientes: TransaccionResumen[];
  resumen: {
    puede_cancelar: boolean;
    dashboard_ready: boolean;
  };
};

export type FetchUsuarioResumenResult =
  | { ok: true; data: UsuarioResumen }
  | { ok: false; status?: number; error: string };

/** Trunca un identificador Stripe para logs: prefijo + sufijo, sin filtrar el ID completo. */
function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

/**
 * Consulta el resumen del usuario en el backend (read-only).
 *
 * - Firma el body JSON con HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET).
 * - Lee BACKEND_URL e INTERNAL_BRIDGE_SECRET de env; nunca los expone al
 *   resultado.
 * - Distingue 401/404/timeout/etc en `result.status` para que el caller
 *   pueda mapearlos al cliente apropiadamente (no devolvemos ok=false con
 *   una sola categoría como en el bridge de webhooks).
 * - Logs no incluyen subscription_id completo (regla T1.4.D guardrail #2).
 *
 * Llamarla solo desde código server-side (route handlers de Next), nunca
 * desde el cliente: imprime el secret en el HMAC.
 */
export async function fetchUsuarioResumen(
  subscriptionId: string,
): Promise<FetchUsuarioResumenResult> {
  const backendUrl = process.env.BACKEND_URL?.trim();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();

  if (!backendUrl) {
    console.error(
      "[BRIDGE] BACKEND_URL no configurada — no se puede consultar usuario-resumen",
    );
    return { ok: false, error: "backend_url_missing" };
  }
  if (!secret) {
    console.error(
      "[BRIDGE] INTERNAL_BRIDGE_SECRET no configurada — no se puede consultar usuario-resumen",
    );
    return { ok: false, error: "internal_bridge_secret_missing" };
  }
  if (!subscriptionId) {
    return { ok: false, error: "missing_subscription_id" };
  }

  // El body que firmamos es exactamente el body que enviamos.
  const body = JSON.stringify({ subscription_id: subscriptionId });
  const signature = crypto
    .createHmac("sha256", secret)
    .update(body, "utf8")
    .digest("hex");

  const url = `${backendUrl.replace(/\/+$/, "")}/internal/usuario-resumen`;
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
      const data = (await res.json()) as UsuarioResumen;
      return { ok: true, data };
    }

    // No-2xx: propagar status para que el route handler decida 502/504/etc.
    // No incluimos preview del body en el log para no filtrar nada del backend.
    console.error(
      `[BRIDGE] usuario-resumen status=${res.status} sub=${shortId(subscriptionId)}`,
    );
    return { ok: false, status: res.status, error: `backend_${res.status}` };
  } catch (err) {
    const isAbort =
      err instanceof Error &&
      (err.name === "AbortError" || err.message.includes("aborted"));
    if (isAbort) {
      console.error(
        `[BRIDGE] Timeout (${BRIDGE_TIMEOUT_MS}ms) usuario-resumen sub=${shortId(subscriptionId)}`,
      );
      return { ok: false, error: "timeout" };
    }
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE] usuario-resumen fetch falló: ${msg}`);
    return { ok: false, error: "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}
