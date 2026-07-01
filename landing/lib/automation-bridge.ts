// landing/lib/automation-bridge.ts — Bridge HMAC para Action Center (T2.1.B)
//
// Mismo patrón que internal-bridge.ts:fetchUsuarioResumen · firma con
// HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET) y llama
// /internal/automation/* en el backend Render.
//
// Reglas:
//   - subscription_id viene SIEMPRE de auth() server-side (T1.4.D).
//   - INTERNAL_BRIDGE_SECRET nunca llega al cliente.
//   - El backend resuelve telefono desde subscription_id y verifica
//     ownership de la accion_id (anti-IDOR).

import "server-only";

import crypto from "node:crypto";

import type {
  AccionApiResult,
  AccionesResponse,
  EjecutarResponse,
  GenerarResponse,
  OportunidadesConEstadoResponse,
  AccionAutomatizacion,
  HighPreviewResponse,
} from "./automation-types";

const BRIDGE_TIMEOUT_MS = 8000;


function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function generarRequestId(): string {
  return "lnd_" + crypto.randomBytes(6).toString("hex");
}


async function callInternal<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<AccionApiResult<T>> {
  const backendUrl = process.env.BACKEND_URL?.trim();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();

  if (!backendUrl) {
    console.error(`[BRIDGE-AUT] BACKEND_URL no configurada (path=${path})`);
    return { ok: false, error: "backend_url_missing" };
  }
  if (!secret) {
    console.error(
      `[BRIDGE-AUT] INTERNAL_BRIDGE_SECRET no configurada (path=${path})`,
    );
    return { ok: false, error: "internal_bridge_secret_missing" };
  }

  const bodyStr = JSON.stringify(body);
  const signature = crypto
    .createHmac("sha256", secret)
    .update(bodyStr, "utf8")
    .digest("hex");

  const url = `${backendUrl.replace(/\/+$/, "")}${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BRIDGE_TIMEOUT_MS);
  const reqId = generarRequestId();

  const subShort = body.subscription_id
    ? shortId(String(body.subscription_id))
    : "-";

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
      const data = (await res.json()) as T;
      return { ok: true, data };
    }
    console.error(
      `[BRIDGE-AUT] ${path} rid=${reqId} status=${res.status} sub=${subShort}`,
    );
    return { ok: false, status: res.status, error: `backend_${res.status}` };
  } catch (err) {
    const isAbort =
      err instanceof Error &&
      (err.name === "AbortError" || err.message.includes("aborted"));
    if (isAbort) {
      console.error(
        `[BRIDGE-AUT] ${path} rid=${reqId} timeout sub=${subShort}`,
      );
      return { ok: false, error: "timeout" };
    }
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE-AUT] ${path} rid=${reqId} fetch falló: ${msg}`);
    return { ok: false, error: "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}


export async function fetchOportunidades(
  subscriptionId: string,
): Promise<AccionApiResult<OportunidadesConEstadoResponse>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  // El backend devuelve oportunidades + estado del perfil (perfil_estado,
  // campos llenos/totales, siguiente paso) para que el dashboard explique
  // POR QUÉ no hay oportunidades cuando el diagnóstico está incompleto.
  return callInternal<OportunidadesConEstadoResponse>(
    "/internal/automation/oportunidades",
    { subscription_id: subscriptionId },
  );
}


export async function fetchAcciones(
  subscriptionId: string,
  estado?: string,
): Promise<AccionApiResult<AccionesResponse>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  const body: Record<string, unknown> = { subscription_id: subscriptionId };
  if (estado) body.estado = estado;
  return callInternal<AccionesResponse>(
    "/internal/automation/acciones",
    body,
  );
}


export async function generarAcciones(
  subscriptionId: string,
): Promise<AccionApiResult<GenerarResponse>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  return callInternal<GenerarResponse>(
    "/internal/automation/acciones/generar",
    { subscription_id: subscriptionId },
  );
}


export async function aprobarAccion(
  subscriptionId: string,
  accionId: number,
): Promise<AccionApiResult<{ accion: AccionAutomatizacion }>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  if (!Number.isInteger(accionId)) {
    return { ok: false, error: "invalid_accion_id" };
  }
  return callInternal<{ accion: AccionAutomatizacion }>(
    "/internal/automation/acciones/aprobar",
    { subscription_id: subscriptionId, accion_id: accionId },
  );
}


export async function rechazarAccion(
  subscriptionId: string,
  accionId: number,
): Promise<AccionApiResult<{ accion: AccionAutomatizacion }>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  if (!Number.isInteger(accionId)) {
    return { ok: false, error: "invalid_accion_id" };
  }
  return callInternal<{ accion: AccionAutomatizacion }>(
    "/internal/automation/acciones/rechazar",
    { subscription_id: subscriptionId, accion_id: accionId },
  );
}


export async function ejecutarAccion(
  subscriptionId: string,
  accionId: number,
): Promise<AccionApiResult<EjecutarResponse>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  if (!Number.isInteger(accionId)) {
    return { ok: false, error: "invalid_accion_id" };
  }
  return callInternal<EjecutarResponse>(
    "/internal/automation/acciones/ejecutar",
    { subscription_id: subscriptionId, accion_id: accionId },
  );
}


export async function obtenerPreviewHigh(
  subscriptionId: string,
  accionId: number,
): Promise<AccionApiResult<HighPreviewResponse>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  if (!Number.isInteger(accionId)) {
    return { ok: false, error: "invalid_accion_id" };
  }
  return callInternal<HighPreviewResponse>(
    "/internal/automation/acciones/high-preview",
    { subscription_id: subscriptionId, accion_id: accionId },
  );
}


export async function confirmarHighDedicado(
  subscriptionId: string,
  accionId: number,
  confirmacion: string,
): Promise<AccionApiResult<EjecutarResponse>> {
  if (!subscriptionId) return { ok: false, error: "missing_subscription_id" };
  if (!Number.isInteger(accionId)) {
    return { ok: false, error: "invalid_accion_id" };
  }
  return callInternal<EjecutarResponse>(
    "/internal/automation/acciones/high-confirmar",
    {
      subscription_id: subscriptionId,
      accion_id: accionId,
      confirmacion,
    },
  );
}
