// landing/lib/reportes-bridge.ts — Bridge HMAC para Reportes/Medición (Fase 1)
//
// Mismo patrón que assets-bridge.ts · firma con
// HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET) y llama /internal/reportes en el
// backend Render.
//
// Reglas:
//   - subscription_id viene SIEMPRE de auth() server-side (T1.4.D).
//   - INTERNAL_BRIDGE_SECRET nunca llega al cliente.
//   - El backend resuelve telefono desde subscription_id y sólo agrega datos
//     de ese telefono (anti-IDOR).

import "server-only";

import crypto from "node:crypto";

import type {
  PeriodoReporte,
  ReportesApiResult,
  ReportesResponse,
} from "./reportes-types";

const BRIDGE_TIMEOUT_MS = 8000;


function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function generarRequestId(): string {
  return "lnd_" + crypto.randomBytes(6).toString("hex");
}


/**
 * Consulta los números de negocio del usuario en el backend (read-only).
 *
 * - Firma el body JSON con HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET).
 * - Lee BACKEND_URL e INTERNAL_BRIDGE_SECRET de env; nunca los expone al
 *   resultado.
 * - Propaga `status` para que el route handler mapee 404/401/timeout.
 * - Logs no incluyen subscription_id completo.
 *
 * Llamar sólo desde código server-side (route handlers), nunca desde el
 * cliente: imprime el secret en el HMAC.
 */
export async function fetchReportes(
  subscriptionId: string,
  opts?: { periodo?: PeriodoReporte },
): Promise<ReportesApiResult> {
  const backendUrl = process.env.BACKEND_URL?.trim();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();

  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  if (!backendUrl) {
    console.error("[BRIDGE-REPORTES] BACKEND_URL no configurada");
    return { ok: false, error: "backend_url_missing" };
  }
  if (!secret) {
    console.error("[BRIDGE-REPORTES] INTERNAL_BRIDGE_SECRET no configurada");
    return { ok: false, error: "internal_bridge_secret_missing" };
  }

  const payload: Record<string, unknown> = { subscription_id: subscriptionId };
  if (opts?.periodo) payload.periodo = opts.periodo;

  // El body que firmamos es exactamente el body que enviamos.
  const bodyStr = JSON.stringify(payload);
  const signature = crypto
    .createHmac("sha256", secret)
    .update(bodyStr, "utf8")
    .digest("hex");

  const url = `${backendUrl.replace(/\/+$/, "")}/internal/reportes`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BRIDGE_TIMEOUT_MS);
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
      const data = (await res.json()) as ReportesResponse;
      return { ok: true, data };
    }

    console.error(
      `[BRIDGE-REPORTES] rid=${reqId} status=${res.status} sub=${subShort}`,
    );
    return { ok: false, status: res.status, error: `backend_${res.status}` };
  } catch (err) {
    const isAbort =
      err instanceof Error &&
      (err.name === "AbortError" || err.message.includes("aborted"));
    if (isAbort) {
      console.error(
        `[BRIDGE-REPORTES] rid=${reqId} timeout (${BRIDGE_TIMEOUT_MS}ms) sub=${subShort}`,
      );
      return { ok: false, error: "timeout" };
    }
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE-REPORTES] rid=${reqId} fetch falló: ${msg}`);
    return { ok: false, error: "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}
