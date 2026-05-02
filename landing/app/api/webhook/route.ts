import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { getStripe } from "@/lib/stripe";
import { sendWhatsAppMessage } from "@/lib/whatsapp";
import { reenviarEventoStripeABackend } from "@/lib/internal-bridge";

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
  } catch (err: any) {
    console.error("Webhook signature verification failed:", err.message);
    return NextResponse.json(
      { error: "Invalid signature" },
      { status: 400 }
    );
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      console.log(
        `Payment successful for ${session.customer_email} — plan: ${session.metadata?.plan}`
      );

      // Extract phone from metadata or from phone_number_collection
      const phone =
        session.metadata?.phone ||
        (session as any).customer_details?.phone ||
        "";

      if (phone) {
        const welcomeMessage =
          "Hola! Soy Dona, tu nueva asistente. " +
          "Tu suscripcion esta activa. " +
          "Escribeme cuando quieras para empezar.";

        const sent = await sendWhatsAppMessage(phone, welcomeMessage);
        if (sent) {
          console.log(`Welcome WhatsApp sent to ${phone}`);
        } else {
          console.warn(`Failed to send WhatsApp to ${phone}`);
        }
      }
      break;
    }

    case "payment_intent.payment_failed": {
      const intent = event.data.object as Stripe.PaymentIntent;
      console.error(
        `Payment failed for ${intent.id}: ${intent.last_payment_error?.message}`
      );
      // Do NOT send any WhatsApp message on failure
      break;
    }

    default:
      // Unhandled event type
      break;
  }

  // Bridge T1.3.E: reenviar el evento verificado al backend Dona.
  // El backend (procesar_evento_suscripcion) maneja la persistencia de
  // suscripciones y la acreditación de créditos. Si el bridge falla,
  // respondemos 500 a Stripe para que reintente (mejor retry + alerta
  // que perder un evento).
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
