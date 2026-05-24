// Allowlist temporal del Control Room interno.
// Nota: esto corre en cliente y NO es una frontera de seguridad real.
// El MVP solo muestra datos estáticos/no secretos. Si el Control Room
// empieza a exponer información sensible, mover el gate a server-side.
const CONTROL_ROOM_EMAILS = new Set(["celestinojbm@gmail.com"]);

export function puedeVerControlRoomInterno(email?: string | null): boolean {
  if (!email) return false;
  return CONTROL_ROOM_EMAILS.has(email.trim().toLowerCase());
}
