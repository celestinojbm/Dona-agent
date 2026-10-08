// landing/app/api/whatsapp-webhook/route.ts — Webhook de WhatsApp (retirado).
//
// Antes reenviaba GET (verificación de Meta) y POST (mensajes) al backend
// en Render, con la URL fija en el código. Dona está en pausa y WhatsApp
// queda como canal opcional futuro, desconectado: la ruta responde 410
// (Gone) sin leer el cuerpo ni hacer ningún fetch.
//
// El 410 también le indica al proveedor que deje de reintentar. Quitar la
// URL del webhook en Whapi/Meta lo hace Celestino (ver
// docs/transition/dona-app-first/ACCIONES-CELESTINO.md).

import { respuestaPausa } from "@/lib/pausa-api";

export async function GET() {
  return respuestaPausa(410);
}

export async function POST() {
  return respuestaPausa(410);
}
