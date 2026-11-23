// landing/app/api/lista-espera/route.ts — Alta en la lista de espera (#334).
//
// Abierta durante la pausa (no vende, no cobra, no da acceso). Campo trampa
// `empresa`: si viene relleno es un bot; respondemos 200 sin guardar nada.

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
  return respuestaDesdeBridge(await registrarEnListaEspera(cuerpo.email.trim(), ipCliente(req)));
}
