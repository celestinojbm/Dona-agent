// landing/app/api/waitlist/route.ts — Lista de espera (plazas completas).
//
// Única ruta API que sigue abierta durante la pausa: registra un correo (y
// opcionalmente un teléfono) para avisar cuando haya plazas. No consulta
// Stripe, el backend ni la sesión. Ver lib/lista-espera.ts.
//
// Respuestas (siempre Cache-Control: no-store):
//   200 { ok: true }                      registrado (o ya estaba, o honeypot)
//   400 { error: "datos_invalidos" }      email/teléfono inválido o cuerpo malo
//   413 { error: "demasiado_grande" }
//   503 { error: "no_disponible" }        faltan SUPABASE_* en el servidor
//   502 { error: "no_guardado" }          Supabase no aceptó la escritura

import { NextResponse } from "next/server";
import {
  MAX_CUERPO,
  guardarEnListaDeEspera,
  normalizarEmail,
  normalizarTelefono,
} from "@/lib/lista-espera";

function responder(cuerpo: Record<string, unknown>, status: number): NextResponse {
  return NextResponse.json(cuerpo, { status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(req: Request) {
  const largo = Number(req.headers.get("content-length") ?? "0");
  if (largo > MAX_CUERPO) return responder({ error: "demasiado_grande" }, 413);

  let texto: string;
  try {
    texto = await req.text();
  } catch {
    return responder({ error: "datos_invalidos" }, 400);
  }
  if (texto.length > MAX_CUERPO) return responder({ error: "demasiado_grande" }, 413);

  let datos: unknown;
  try {
    datos = JSON.parse(texto);
  } catch {
    return responder({ error: "datos_invalidos" }, 400);
  }
  if (!datos || typeof datos !== "object" || Array.isArray(datos)) {
    return responder({ error: "datos_invalidos" }, 400);
  }
  const d = datos as Record<string, unknown>;

  // Honeypot: un humano no ve ni rellena "empresa". A un bot se le responde
  // como si todo hubiera ido bien, sin guardar nada.
  if (typeof d.empresa === "string" && d.empresa.trim() !== "") {
    return responder({ ok: true }, 200);
  }

  const email = normalizarEmail(d.email);
  const phone = normalizarTelefono(d.phone);
  if (!email || phone === null) return responder({ error: "datos_invalidos" }, 400);

  const resultado = await guardarEnListaDeEspera({ email, ...(phone ? { phone } : {}) });
  if (resultado === "sin_configuracion") return responder({ error: "no_disponible" }, 503);
  if (resultado === "error") return responder({ error: "no_guardado" }, 502);
  return responder({ ok: true }, 200);
}
