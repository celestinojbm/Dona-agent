// landing/lib/auth-lockout-bridge.ts — Bridge HMAC para lockout de login (rank 4)
//
// Espeja automation-bridge.ts: firma el body con
// HMAC-SHA256(INTERNAL_BRIDGE_SECRET) y llama /internal/auth/login-* en el
// backend Render. Se usa desde auth.ts (authorize de NextAuth), server-side.
//
// El estado de lockout (intentos fallidos + bloqueo) vive en el backend porque
// la landing corre en Vercel serverless y no mantiene estado entre instancias.
//
// Diseño FAIL-OPEN: si el backend no responde o no está configurado, el CHECK
// devuelve no-bloqueado — no dejamos a un usuario fuera de su dashboard por un
// hiccup del backend; la ventana de brute-force durante una caída es mínima.
// Un RECORD que falla simplemente no cuenta ese intento.

import "server-only";

import crypto from "node:crypto";

const BRIDGE_TIMEOUT_MS = 8000;

export interface LockoutEstado {
  bloqueado: boolean;
  retry_after_segundos: number;
}

async function callInternalAuth(
  path: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const backendUrl = process.env.BACKEND_URL?.trim();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();

  if (!backendUrl || !secret) {
    // Fail-open: sin bridge configurado no podemos consultar el lockout.
    console.error(`[BRIDGE-AUTH] bridge no configurado (path=${path})`);
    return null;
  }

  const bodyStr = JSON.stringify(body);
  const signature = crypto
    .createHmac("sha256", secret)
    .update(bodyStr, "utf8")
    .digest("hex");

  const url = `${backendUrl.replace(/\/+$/, "")}${path}`;
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
      console.error(`[BRIDGE-AUTH] ${path} status=${res.status}`);
      return null;
    }
    return (await res.json()) as Record<string, unknown>;
  } catch (err) {
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[BRIDGE-AUTH] ${path} fetch falló: ${msg}`);
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Consulta si el email está bloqueado por brute-force. No muta estado.
 * Fail-open: ante cualquier fallo del bridge, devuelve no-bloqueado.
 */
export async function checkLoginLockout(email: string): Promise<LockoutEstado> {
  if (!email) return { bloqueado: false, retry_after_segundos: 0 };
  const data = await callInternalAuth("/internal/auth/login-check", { email });
  if (!data) return { bloqueado: false, retry_after_segundos: 0 };
  return {
    bloqueado: Boolean(data.bloqueado),
    retry_after_segundos: Number(data.retry_after_segundos) || 0,
  };
}

/**
 * Registra el resultado de un intento de login: `exito=true` resetea el
 * contador, `exito=false` lo incrementa y bloquea al alcanzar el umbral.
 * Best-effort: si el bridge falla, el intento simplemente no se cuenta.
 */
export async function recordLoginAttempt(
  email: string,
  exito: boolean,
): Promise<void> {
  if (!email) return;
  await callInternalAuth("/internal/auth/login-record", { email, exito });
}
