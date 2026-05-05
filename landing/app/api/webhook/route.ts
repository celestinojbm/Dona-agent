import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { getStripe } from "@/lib/stripe";
import { reenviarEventoStripeABackend } from "@/lib/internal-bridge";

// T2.0.B · El welcome WhatsApp post-checkout YA NO se envía desde acá.
// El backend (agent/welcome.py · enviar_bienvenida_premium) lo envía
// canónicamente tras crear SuscripcionStripe en T1.3.C, con password
// derivado, link al dashboard e idempotencia por flag bienvenida_enviada.
// Eliminado para evitar doble WhatsApp si Stripe reintenta el webhook.

export async function POST(req: NextRequest) {
  const body = await req.text();
  const sig = req.headers.get("stripe-signature");

  if (!sig) {
    return NextResponse.json({ error: "Missing signature" }, { status: 400 });
  }

  let event: Stripe.Event;

  try {
    event = getStripe().webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "unknown";
    console.error("Webhook signature verification failed:", msg);
    return NextResponse.json(
      { error: "Invalid signature" },
      { status: 400 }
    );
  }

  // Logueamos solo metadata semántica, no PII. El welcome lo maneja el backend.
  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      console.log(
        `[WEBHOOK] checkout.session.completed plan=${session.metadata?.plan ?? "—"} ` +
          `mode=${session.mode}`,
      );
      break;
    }

    case "payment_intent.payment_failed": {
      const intent = event.data.object as Stripe.PaymentIntent;
      console.error(
        `[WEBHOOK] payment_intent.payment_failed id=${intent.id}: ` +
          `${intent.last_payment_error?.message ?? "—"}`,
      );
      break;
    }

    default:
      // Unhandled event type — el bridge igual lo reenvía al backend.
      break;
  }

  // Bridge T1.3.E: reenviar el evento verificado al backend Dona.
  // El backend (procesar_evento_suscripcion) maneja la persistencia de
  // suscripciones, la acreditación de créditos, y desde T2.0.B también
  // el welcome con password. Si el bridge falla, respondemos 500 a
  // Stripe para que reintente (mejor retry + alerta que perder un evento).
  const bridge = await reenviarEventoStripeABackend(event);
  if (!bridge.ok) {
    console.error(
      `[WEBHOOK] Bridge a backend falló (status=${bridge.status ?? "n/a"} ` +
        `error=${bridge.error}). Respondiendo 500 a Stripe para retry.`,
    );
    return NextResponse.json(
      { error: "bridge_failed", reason: bridge.error },
      { status: 500 },
    );
  }

  return NextResponse.json({ received: true });
}
