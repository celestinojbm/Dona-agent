// landing/app/api/lista-espera/invitacion/route.ts — Canje de invitación (#334).
//
// El código se valida en el backend (DONA_CODIGOS_INVITACION, con bloqueo
// por intentos fallidos). Reserva el lugar; no da acceso mientras dure la pausa.

import { canjearInvitacion } from "@/lib/lista-espera-bridge";
import { emailValido, ipCliente, leerCuerpo, respuesta, respuestaDesdeBridge } from "@/lib/lista-espera";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const cuerpo = await leerCuerpo(req);
  if (!cuerpo) return respuesta({ ok: false, error: "solicitud_invalida" }, 400);
  if (!emailValido(cuerpo.email)) return respuesta({ ok: false, error: "email_invalido" }, 400);
  const codigo = typeof cuerpo.codigo === "string" ? cuerpo.codigo.trim() : "";
  if (codigo.length < 8 || codigo.length > 64) {
    return respuesta({ ok: false, error: "codigo_invalido" }, 403);
  }
  return respuestaDesdeBridge(await canjearInvitacion(cuerpo.email.trim(), codigo, ipCliente(req)));
}
