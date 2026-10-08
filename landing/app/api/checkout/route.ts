// landing/app/api/checkout/route.ts — Checkout de suscripciones y top-ups.
//
// Dona está en pausa: esta ruta NO crea sesiones de Stripe, ni con price ID
// ni con price_data inline. Responde 503 antes de leer el body, la sesión o
// cualquier variable de Stripe, así que no depende de cómo estén las env de
// Vercel.
//
// La implementación comercial anterior (suscripción embebida/hospedada y
// top-ups) queda en el historial de git. Volver a cobrar es un PR de
// relanzamiento aparte, no un cambio de flag.

import { respuestaPausa } from "@/lib/pausa-api";

export async function POST() {
  return respuestaPausa();
}
