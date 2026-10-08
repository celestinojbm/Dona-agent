// landing/lib/app-bridge.ts — Bridge firmado landing → /internal/app (J7.5).
//
// Mismo contrato que los demás bridges: el body JSON se firma con
// HMAC-SHA256(body, INTERNAL_BRIDGE_SECRET) y se envía tal cual. La identidad
// (usuario_id, workspace_id) la pone el servidor desde la sesión, nunca el
// navegador; el backend vuelve a validar la membresía.
//
// Los payloads pueden llevar email y contraseña (auth.*): nunca se loguean.
// Solo se registran la acción, el status y el request id.
import "server-only";

import crypto from "node:crypto";
import { resolverBackendUrl } from "@/lib/backend-url";
import type { ResultadoApp } from "@/lib/app-types";

const TIMEOUT_MS = 8000;
const ACCION_VALIDA = /^[a-z]+(\.[a-z]+)?$/;

export async function llamarApp<T>(
  accion: string,
  payload: Record<string, unknown>,
): Promise<ResultadoApp<T>> {
  if (!ACCION_VALIDA.test(accion)) return { ok: false, error: "accion_invalida" };
  const backendUrl = resolverBackendUrl();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();
  if (!backendUrl) return { ok: false, error: "backend_url_missing" };
  if (!secret) return { ok: false, error: "internal_bridge_secret_missing" };

  const body = JSON.stringify(payload);
  const firma = crypto.createHmac("sha256", secret).update(body, "utf8").digest("hex");
  const reqId = "lnd_" + crypto.randomBytes(6).toString("hex");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(`${backendUrl}/internal/app/${accion}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Signature": firma,
        "X-Request-ID": reqId,
      },
      body,
      signal: controller.signal,
      cache: "no-store",
    });
    let cuerpo: Record<string, unknown> = {};
    try {
      cuerpo = (await res.json()) as Record<string, unknown>;
    } catch {
      // cuerpo no JSON: se trata como error opaco
    }
    if (res.ok) return { ok: true, data: cuerpo as T };
    console.error(`[APP-BRIDGE] ${accion} rid=${reqId} status=${res.status}`);
    return {
      ok: false,
      status: res.status,
      error: typeof cuerpo.error === "string" ? cuerpo.error : `backend_${res.status}`,
      detalle: typeof cuerpo.detalle === "string" ? cuerpo.detalle : undefined,
    };
  } catch (err) {
    const abortado =
      err instanceof Error && (err.name === "AbortError" || err.message.includes("aborted"));
    console.error(`[APP-BRIDGE] ${accion} rid=${reqId} ${abortado ? "timeout" : "fetch falló"}`);
    return { ok: false, error: abortado ? "timeout" : "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}
