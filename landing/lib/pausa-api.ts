// landing/lib/pausa-api.ts — Respuestas de las rutas API durante la pausa.
//
// Uso al INICIO de cada handler, antes de leer el body, la sesión o llamar
// a cualquier servicio externo:
//
//   const pausa = bloqueoPausa();
//   if (pausa) return pausa;
//
// Así la ruta no consulta Stripe, el backend ni la sesión mientras Dona
// está en pausa (ver lib/pausa.ts).

import { NextResponse } from "next/server";
import { CUERPO_PAUSA, DONA_EN_PAUSA } from "@/lib/pausa";

/** Respuesta de pausa. 503 por defecto; 410 para canales retirados. */
export function respuestaPausa(status: 410 | 503 = 503): NextResponse {
  return NextResponse.json(CUERPO_PAUSA, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

/** Si Dona está en pausa, la respuesta que debe devolver la ruta; si no, null. */
export function bloqueoPausa(status: 410 | 503 = 503): NextResponse | null {
  return DONA_EN_PAUSA ? respuestaPausa(status) : null;
}

/**
 * Para superficies internas retiradas durante la pausa (panel de
 * ingeniería): responden 404 como si no existieran, sin revelar que hay
 * un panel detrás.
 */
export function rutaRetiradaEnPausa(): NextResponse | null {
  return DONA_EN_PAUSA
    ? NextResponse.json(
        { error: "not_found" },
        { status: 404, headers: { "Cache-Control": "no-store" } },
      )
    : null;
}
