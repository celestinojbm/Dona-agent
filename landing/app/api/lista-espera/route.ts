// landing/app/api/lista-espera/route.ts — Alta en la lista de espera (#334).
//
// Abierta durante la pausa (no vende, no cobra, no da acceso). Campo trampa
// `empresa`: si viene relleno es un bot; respondemos 200 sin guardar nada.
//
// La respuesta pública del alta es siempre "en_espera": si devolviera el
// estado real, cualquiera podría comprobar si un correo ajeno canjeó una
// invitación. El estado "invitado" solo se muestra al canjear un código.

import { registrarEnListaEspera } from "@/lib/lista-espera-bridge";
import { emailValido, ipCliente, leerCuerpo, respuesta, respuestaDesdeBridge } from "@/lib/lista-espera";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const cuerpo = await leerCuerpo(req);
  if (!cuerpo) return respuesta({ ok: false, error: "solicitud_invalida" }, 400);
  if (typeof cuerpo.empresa === "string" && cuerpo.empresa.trim()) {
    return respuesta({ ok: true, estado: "en_espera" }, 200);
  }
  if (!emailValido(cuerpo.email)) return respuesta({ ok: false, error: "email_invalido" }, 400);
  const r = await registrarEnListaEspera(cuerpo.email.trim(), ipCliente(req));
  return respuestaDesdeBridge(r.ok ? { ok: true, estado: "en_espera" } : r);
}
