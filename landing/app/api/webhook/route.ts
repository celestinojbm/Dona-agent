// landing/app/api/webhook/route.ts — Webhook de Stripe durante la pausa.
//
// Contrato en pausa:
//   - Sin STRIPE_WEBHOOK_SECRET → 503 y NO se acepta el evento (nunca se
//     procesa un evento sin validar). Celestino debe deshabilitar el
//     endpoint en Stripe en ese caso.
//   - Sin cabecera stripe-signature o con firma inválida → 400.
//   - Evento con firma válida → 200 {received, paused} SIN acciones
//     comerciales y SIN bridge al backend. Así Stripe deja de reintentar
//     (antes el bridge fallaba contra Render suspendido → 500 → reintentos
//     durante 3 días).
//
// La verificación usa Stripe.webhooks (estático): NO necesita
// STRIPE_SECRET_KEY, que puede retirarse de Vercel.
//
// Evidencia: solo se registra en el log id, tipo, livemode y created del
// evento. Nunca el payload (puede traer emails, teléfonos, importes).
//
// Este acuse NO reconcilia la base de datos: la conciliación de cierre se
// hace contra Stripe (ver docs/transition/dona-app-first/).

import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";

export async function POST(req: NextRequest) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET?.trim();
  if (!secret) {
    console.error(
      "[WEBHOOK-PAUSA] STRIPE_WEBHOOK_SECRET no configurada · evento rechazado sin validar",
    );
    return NextResponse.json(
      { error: "webhook_no_configurado" },
      { status: 503 },
    );
  }

  const sig = req.headers.get("stripe-signature");
  if (!sig) {
    return NextResponse.json({ error: "Missing signature" }, { status: 400 });
  }

  const body = await req.text();

  let event: Stripe.Event;
  try {
    event = Stripe.webhooks.constructEvent(body, sig, secret);
  } catch {
    // Sin detalles del error en el log: pueden incluir fragmentos del cuerpo.
    console.warn("[WEBHOOK-PAUSA] firma inválida · evento rechazado");
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  console.log(
    `[WEBHOOK-PAUSA] evento recibido sin procesar · id=${event.id} ` +
      `type=${event.type} livemode=${event.livemode} created=${event.created}`,
  );

  return NextResponse.json({ received: true, paused: true });
}
