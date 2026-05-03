// landing/lib/dashboard-auth.ts
// T1.4.B — Validación de password de dashboard.
//
// Antes de T1.4.B la función `authorize` en auth.ts recibía el password
// pero nunca lo validaba: cualquiera con un email de subscriber podía
// entrar. Este módulo deriva un password único por usuario a partir de
// su Stripe customer_id y un secret compartido (DASHBOARD_PASSWORD_SECRET).
//
// Diseño:
//   - Sin storage adicional. El password no se persiste en DB.
//   - Determinístico: mismo customer_id + mismo secret → mismo password.
//   - Resistente a brute force: el secret tiene entropía alta (32+ bytes),
//     y cada intento requiere conocer un email + customer_id válido.
//   - Comparación en tiempo constante para evitar timing oracles.
//   - Sin secret configurado: deriveDashboardPassword retorna null y el
//     login falla. NO hay path permisivo (mejor bloquear que abrir).

import crypto from "node:crypto";

const PASSWORD_PREFIX = "dona-";
const PASSWORD_SUFFIX_LENGTH = 12;

/**
 * Deriva el password de dashboard para un Stripe customer_id.
 *
 * password = "dona-" + hex(HMAC-SHA256(customer_id, secret))[:12]
 *
 * Retorna null si DASHBOARD_PASSWORD_SECRET no está configurada o si
 * customer_id está vacío.
 */
export function deriveDashboardPassword(customerId: string): string | null {
  const secret = process.env.DASHBOARD_PASSWORD_SECRET?.trim();
  if (!secret || !customerId) return null;
  const digest = crypto
    .createHmac("sha256", secret)
    .update(customerId, "utf8")
    .digest("hex");
  return PASSWORD_PREFIX + digest.slice(0, PASSWORD_SUFFIX_LENGTH);
}

/**
 * Compara dos strings en tiempo constante. Si las longitudes difieren
 * retorna false sin filtrar info (no usa timingSafeEqual con buffers de
 * tamaños distintos porque tira excepción). Cualquier excepción interna
 * se traga retornando false — el caller solo ve "no coincidió".
 */
export function constantTimeEqual(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  try {
    const ab = Buffer.from(a, "utf8");
    const bb = Buffer.from(b, "utf8");
    if (ab.length !== bb.length) return false;
    return crypto.timingSafeEqual(ab, bb);
  } catch {
    return false;
  }
}
