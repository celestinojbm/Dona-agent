// landing/lib/control-room.ts — Quién puede abrir el Control Room interno.
//
// Solo servidor: `server-only` hace fallar el build si un componente cliente
// lo importa. Así la allowlist (correos del equipo) nunca viaja en el bundle
// JS que descarga cualquier usuario, y el gate se evalúa en el servidor
// antes de renderizar nada del panel (ver app/interno/control-room/page.tsx).
//
// Ocultar el enlace en el menú no es una frontera de seguridad; esto sí.

import "server-only";

const CONTROL_ROOM_EMAILS = new Set(["celestinojbm@gmail.com"]);

export function puedeVerControlRoomInterno(email?: string | null): boolean {
  if (!email) return false;
  return CONTROL_ROOM_EMAILS.has(email.trim().toLowerCase());
}
