// landing/lib/lista-espera-bridge.ts — Bridge HMAC de la lista de espera (#334).
//
// Mismo patrón que reportes-bridge.ts: firma HMAC-SHA256(body,
// INTERNAL_BRIDGE_SECRET) y llama /internal/lista-espera[/invitacion] en el
// backend. Solo servidor: el secret nunca llega al cliente. La IP del
// visitante viaja dentro del cuerpo firmado (límites por IP del backend). Los
// logs no incluyen el correo, el código ni la IP.

import "server-only";

import crypto from "node:crypto";

import { resolverBackendUrl } from "@/lib/backend-url";

const BRIDGE_TIMEOUT_MS = 8000;

export type EstadoListaEspera = "en_espera" | "invitado";

export type ResultadoListaEspera =
  | { ok: true; estado: EstadoListaEspera }
  | { ok: false; status?: number; error: string };

async function llamar(
  ruta: "/internal/lista-espera" | "/internal/lista-espera/invitacion",
  payload: Record<string, string>,
): Promise<ResultadoListaEspera> {
  const backendUrl = resolverBackendUrl();
  const secret = process.env.INTERNAL_BRIDGE_SECRET?.trim();
  if (!backendUrl) return { ok: false, error: "backend_url_missing" };
  if (!secret) return { ok: false, error: "internal_bridge_secret_missing" };

  const bodyStr = JSON.stringify(payload);
  const signature = crypto.createHmac("sha256", secret).update(bodyStr, "utf8").digest("hex");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BRIDGE_TIMEOUT_MS);
  const reqId = "lnd_" + crypto.randomBytes(6).toString("hex");

  try {
    const res = await fetch(`${backendUrl}${ruta}`, {
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
      const data = (await res.json()) as { estado?: string };
      const estado = data.estado === "invitado" ? "invitado" : "en_espera";
      return { ok: true, estado };
    }
    let detalle = `backend_${res.status}`;
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === "string") detalle = j.detail;
    } catch {
      // cuerpo no JSON: se queda el código genérico
    }
    console.error(`[BRIDGE-LISTA-ESPERA] rid=${reqId} ruta=${ruta} status=${res.status}`);
    return { ok: false, status: res.status, error: detalle };
  } catch (err) {
    const abort = err instanceof Error && (err.name === "AbortError" || err.message.includes("aborted"));
    console.error(`[BRIDGE-LISTA-ESPERA] rid=${reqId} ${abort ? "timeout" : "fetch falló"}`);
    return { ok: false, error: abort ? "timeout" : "fetch_failed" };
  } finally {
    clearTimeout(timeout);
  }
}

export function registrarEnListaEspera(email: string, ip: string) {
  return llamar("/internal/lista-espera", { email, ip });
}

export function canjearInvitacion(email: string, codigo: string, ip: string) {
  return llamar("/internal/lista-espera/invitacion", { email, codigo, ip });
}
