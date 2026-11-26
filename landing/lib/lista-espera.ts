// landing/lib/lista-espera.ts — Validación y respuestas de la lista de espera.
//
// Compartido por /api/lista-espera y /api/lista-espera/invitacion. Las rutas
// siguen abiertas durante la pausa a propósito: no venden, no cobran ni dan
// acceso; solo guardan un correo (y, con código válido, lo marcan invitado).

import { NextResponse } from "next/server";
import type { ResultadoListaEspera } from "@/lib/lista-espera-bridge";

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$/;
const MAX_BODY = 2_000;

export function emailValido(email: unknown): email is string {
  return typeof email === "string" && email.trim().length <= 254 && EMAIL_RE.test(email.trim());
}

/** Lee el JSON del cuerpo con tope de tamaño. null si no es un objeto. */
export async function leerCuerpo(req: Request): Promise<Record<string, unknown> | null> {
  if (!(req.headers.get("content-type") ?? "").includes("application/json")) return null;
  const texto = await req.text();
  if (texto.length > MAX_BODY) return null;
  try {
    const datos: unknown = JSON.parse(texto);
    return datos && typeof datos === "object" && !Array.isArray(datos)
      ? (datos as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function respuesta(cuerpo: Record<string, unknown>, status: number): NextResponse {
  return NextResponse.json(cuerpo, { status, headers: { "Cache-Control": "no-store" } });
}

/** Traduce el resultado del bridge a una respuesta sin detalles internos. */
export function respuestaDesdeBridge(r: ResultadoListaEspera): NextResponse {
  if (r.ok) return respuesta({ ok: true, estado: r.estado }, 200);
  if (r.status === 400) return respuesta({ ok: false, error: "email_invalido" }, 400);
  if (r.status === 403) return respuesta({ ok: false, error: "codigo_invalido" }, 403);
  if (r.status === 429) return respuesta({ ok: false, error: "demasiados_intentos" }, 429);
  return respuesta({ ok: false, error: "no_disponible" }, 503);
}
