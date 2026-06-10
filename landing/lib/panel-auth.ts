// landing/lib/panel-auth.ts
// Auth del panel de ingeniería (/engineering) — token único del dueño.
//
// NO reusa la sesión NextAuth del dashboard: esa autentica a cualquier
// suscriptor de Stripe, y el panel es exclusivo del dueño. En su lugar, un
// secret simple (PANEL_INGENIERIA_TOKEN) que se presenta una vez en el form
// de acceso y viaja después en una cookie httpOnly.
//
// Reglas:
//   - FAIL-CLOSED: sin PANEL_INGENIERIA_TOKEN configurado, nadie entra
//     (a diferencia del lockout del dashboard, que es fail-open: acá el
//     fallo de configuración debe negar acceso, no regalarlo).
//   - Comparación timing-safe (mismo principio que hmac.compare_digest en
//     el backend). Se hashean ambos lados con SHA-256 para igualar
//     longitudes antes de timingSafeEqual.
import "server-only";

import crypto from "node:crypto";

/** Nombre de la cookie httpOnly que guarda el token del panel. */
export const PANEL_COOKIE = "panel_ing_token";

/** Vida de la cookie: 30 días (uso personal, dispositivo del dueño). */
export const PANEL_COOKIE_MAX_AGE = 30 * 24 * 60 * 60;

/**
 * Valida un token candidato contra PANEL_INGENIERIA_TOKEN.
 *
 * Devuelve false si el env var no está configurado, si el candidato está
 * vacío, o si no coincide. Nunca lanza.
 */
export function esTokenPanelValido(candidato: string | undefined | null): boolean {
  const esperado = process.env.PANEL_INGENIERIA_TOKEN?.trim();
  if (!esperado) return false;
  if (!candidato) return false;

  // SHA-256 de ambos lados → buffers de longitud fija → timingSafeEqual
  // no filtra longitud ni contenido por timing.
  const hashEsperado = crypto.createHash("sha256").update(esperado).digest();
  const hashCandidato = crypto.createHash("sha256").update(candidato).digest();
  return crypto.timingSafeEqual(hashEsperado, hashCandidato);
}
