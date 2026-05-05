import { NextRequest, NextResponse } from "next/server";
import {
  getStripe,
  PLANS,
  PAQUETES,
  type PlanKey,
  type PaqueteKey,
} from "@/lib/stripe";

// T1.7 · Checkout dual-mode.
//
// kind="subscription" (default por compat con UI vieja):
//   - body: { plan: "premium"|"pro", phone? }
//   - mode: subscription
//
// kind="topup":
//   - body: { paquete: "100"|"500"|"2000", phone? }
//   - mode: payment (one-time)
//   - metadata.creditos = paquete.creditos para que el backend acredite
//     vía procesar_evento_stripe (legacy path) tras webhook → bridge.

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const kind = (body.kind as string | undefined) || "subscription";
    const phone = (body.phone as string | undefined) || "";
    const origin = req.headers.get("origin") || "http://localhost:3000";

    if (kind === "subscription") {
      return crearCheckoutSuscripcion(body, phone, origin);
    }
    if (kind === "topup") {
      return crearCheckoutTopup(body, phone, origin);
    }

    return NextResponse.json(
      { error: "invalid_kind. Use 'subscription' or 'topup'." },
      { status: 400 },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(`[CHECKOUT] error inesperado: ${msg}`);
    return NextResponse.json(
      { error: "checkout_failed" },
      { status: 500 },
    );
  }
}


async function crearCheckoutSuscripcion(
  body: { plan?: string },
  phone: string,
  origin: string,
) {
  const plan = body.plan;
  if (!plan || !(plan in PLANS)) {
    return NextResponse.json(
      { error: "Invalid plan. Use 'premium' or 'pro'." },
      { status: 400 },
    );
  }

  const selectedPlan = PLANS[plan as PlanKey];

  // Si Stripe price IDs están configurados, usarlos (subscription mode)
  // Si no, fallback a one-time inline price (dev/test sin Stripe Dashboard).
  const lineItems = selectedPlan.priceId
    ? [{ price: selectedPlan.priceId, quantity: 1 }]
    : [
        {
          price_data: {
            currency: "usd" as const,
            product_data: { name: `Dona ${selectedPlan.name}` },
            unit_amount: selectedPlan.price,
            recurring: { interval: "month" as const },
          },
          quantity: 1,
        },
      ];

  const session = await getStripe().checkout.sessions.create({
    mode: "subscription",
    payment_method_types: ["card"],
    line_items: lineItems,
    success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/cancel`,
    metadata: {
      kind: "subscription",
      plan,
      phone,
    },
    phone_number_collection: { enabled: true },
  });

  return NextResponse.json({ url: session.url });
}


async function crearCheckoutTopup(
  body: { paquete?: string },
  phone: string,
  origin: string,
) {
  const paquete = body.paquete;
  if (!paquete || !(paquete in PAQUETES)) {
    return NextResponse.json(
      { error: "invalid_paquete. Use '100', '500' or '2000'." },
      { status: 400 },
    );
  }

  const p = PAQUETES[paquete as PaqueteKey];
  if (!p.priceId) {
    // Owner no configuró el price ID en Vercel para este paquete.
    // No inventamos uno: rechazamos limpio.
    console.error(
      `[CHECKOUT] paquete=${paquete} sin STRIPE_PRICE_PAQUETE_${paquete} configurada`,
    );
    return NextResponse.json(
      { error: "paquete_no_configurado" },
      { status: 503 },
    );
  }

  const session = await getStripe().checkout.sessions.create({
    mode: "payment",
    payment_method_types: ["card"],
    line_items: [{ price: p.priceId, quantity: 1 }],
    success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/cancel`,
    // metadata.creditos es leído por procesar_evento_stripe en el backend
    // tras llegar el webhook checkout.session.completed mode=payment.
    // metadata.telefono es el campo que ese path lee como fallback de
    // client_reference_id.
    metadata: {
      kind: "topup",
      paquete,
      creditos: String(p.creditos),
      telefono: phone,
      phone, // duplicado por compat con el path de subscription
    },
    phone_number_collection: { enabled: true },
  });

  return NextResponse.json({ url: session.url });
}
