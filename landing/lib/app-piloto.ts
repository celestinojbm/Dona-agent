// landing/lib/app-piloto.ts — Puerta del piloto app-first (J7.5).
//
// /app es la Dona app-first: áreas, proyectos, tareas, agentes con permisos,
// aprobaciones y evidencia. Está APAGADA por defecto y es independiente de
// DONA_EN_PAUSA: la web pública sigue en pausa (sin ventas ni cobros) aunque
// el piloto esté abierto para usuarios invitados.
//
// Solo el valor exacto "true" la enciende: una variable vacía, con espacios
// raros o mal escrita deja /app en 404. El backend tiene su propia puerta
// (DONA_APP_PILOTO_ENABLED) y su lista de invitados; hacen falta las dos.

export function appPilotoHabilitado(
  valor: string | undefined = process.env.DONA_APP_PILOTO_ENABLED,
): boolean {
  return valor?.trim() === "true";
}
