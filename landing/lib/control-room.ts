// landing/lib/control-room.ts — Quién puede abrir el Control Room interno.
//
// Solo servidor: `server-only` hace fallar el build si un componente cliente
// lo importa. Así la allowlist (correos del equipo) nunca viaja en el bundle
// JS que descarga cualquier usuario, y el gate se evalúa en el servidor
// antes de renderizar nada del panel (ver app/interno/control-room/page.tsx).
//
// Ocultar el enlace en el menú no es una frontera de seguridad; esto sí.
//
// Por qué no basta el correo de la sesión: la sesión NextAuth del dashboard
// toma el correo del customer de Stripe, que lo escribe quien paga y Stripe
// no lo verifica. El password llega al teléfono de esa suscripción, no al
// correo. Cualquiera que pague con el correo del dueño y su propio teléfono
// obtiene una sesión con ese correo (y, por la recuperación cross-customer
// de lib/auth-matcher.ts, incluso la del customer del dueño). Por eso el
// correo es solo una primera condición: además se exige el token del dueño
// (PANEL_INGENIERIA_TOKEN, cookie httpOnly de lib/panel-auth.ts), el mismo
// que protege /engineering. Fail-closed: sin token configurado, nadie entra.

import "server-only";

import { esTokenPanelValido } from "@/lib/panel-auth";

const CONTROL_ROOM_EMAILS = new Set(["celestinojbm@gmail.com"]);

export function correoEnAllowlist(email?: string | null): boolean {
  if (!email) return false;
  return CONTROL_ROOM_EMAILS.has(email.trim().toLowerCase());
}

export function puedeVerControlRoomInterno(
  email: string | null | undefined,
  tokenPanel: string | null | undefined,
): boolean {
  return correoEnAllowlist(email) && esTokenPanelValido(tokenPanel);
}
