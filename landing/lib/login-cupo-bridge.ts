// landing/lib/login-cupo-bridge.ts — Cupo compartido del login de ingeniería.
//
// La ventana vive en el backend (agent/rate_limiter.py): Redis si REDIS_URL
// conecta, memoria de ese proceso si no. Así todas las instancias de Next
// comparten el mismo tope. Firma HMAC-SHA256(INTERNAL_BRIDGE_SECRET), igual
// que auth-lockout-bridge.ts.
//
// Si el bridge no está configurado o no responde, devuelve null. El caller
// usa la memoria local de esta instancia: no dejamos el login sin tope, y
// tampoco tratamos un fallo de red como "permitido".
//
// El body solo lleva IP y el usuario fijo del panel. Nunca el token.

import "server-only";

import crypto from "node:crypto";
import { resolverBackendUrl } from "@/lib/backend-url";

const BRIDGE_TIMEOUT_MS = 8000;

export type CupoRemoto = {
  permitido: boolean;
  retryAfterSegundos: number;
};

async function postCupo(
  body: Record<string, string>,
): Promise<Record<string, unknown> | null> {
  const backendUrl = resolverBackendUrl();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();
  if (!backendUrl || !secret) {
    console.error("[BRIDGE-PANEL] cupo de login sin bridge configurado");
    return null;
  }

  const bodyStr = JSON.stringify(body);
  const signature = crypto
    .createHmac("sha256", secret)
    .update(bodyStr, "utf8")
    .digest("hex");
  const url = `${backendUrl}/internal/panel/login-cupo`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BRIDGE_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Signature": signature,
      },
      body: bodyStr,
      signal: controller.signal,
    });
    if (!res.ok) {
      console.error(`[BRIDGE-PANEL] login-cupo status=${res.status}`);
      return null;
    }
    const data = (await res.json()) as unknown;
    if (!data || typeof data !== "object") return null;
    return data as Record<string, unknown>;
  } catch (err) {
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE-PANEL] login-cupo fetch falló: ${msg}`);
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Consulta el cupo compartido. null = el caller debe usar memoria local.
 * No interpreta un fallo como intento permitido.
 */
export async function consultarCupoLogin(
  ip: string,
  usuario: string,
): Promise<CupoRemoto | null> {
  const data = await postCupo({ ip, usuario });
  if (!data || typeof data.permitido !== "boolean") return null;
  if (data.permitido) return { permitido: true, retryAfterSegundos: 0 };
  const retry = Number(data.retry_after_segundos);
  const segundos = Number.isFinite(retry) ? Math.ceil(retry) : 1;
  return { permitido: false, retryAfterSegundos: Math.max(1, segundos) };
}
