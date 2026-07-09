import { NextRequest, NextResponse } from "next/server";
import type Stripe from "stripe";
import {
  getStripe,
  PLANS,
  PAQUETES,
  type PlanKey,
  type PaqueteKey,
} from "@/lib/stripe";
import { auth } from "@/auth";
import { fetchUsuarioResumen } from "@/lib/internal-bridge";

// T1.7 · Checkout dual-mode.
//
// kind="subscription" (default por compat con UI vieja):
//   - body: { plan: "premium"|"pro", phone?, embedded? }
//   - mode: subscription
//   - flow PÚBLICO (pre-cuenta). El usuario no tiene sesión todavía.
//     Acepta phone en metadata para que, post-checkout, podamos
//     vincular el customer Stripe al teléfono dado.
//   - embedded=true → Stripe Embedded Checkout (ui_mode: "embedded"): en vez
//     de redirigir a stripe.com, devuelve { clientSecret } y el pago se monta
//     DENTRO de /checkout (app/checkout). El webhook y el fulfillment son los
//     MISMOS (checkout.session.completed con la misma metadata); solo cambia
//     dónde se renderiza el formulario de pago. Sin embedded (default) sigue
//     devolviendo { url } de la página hospedada (compat).
//
// kind="topup":
//   - body: { paquete: "100"|"500"|"2000" }
//   - mode: payment (one-time)
//   - flow AUTENTICADO. Requiere sesión NextAuth válida.
//   - <b>NO acepta phone desde el body</b> (regla de identidad: T1.7
//     follow-up). El teléfono se resuelve server-side desde el backend
//     usando el subscriptionId de la sesión (vía /internal/usuario-resumen).
//   - metadata.creditos = paquete.creditos para que el backend acredite
//     vía procesar_evento_stripe (legacy path) tras webhook → bridge.

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const kind = (body.kind as string | undefined) || "subscription";
    const origin = req.headers.get("origin") || "http://localhost:3000";

    if (kind === "subscription") {
      const phone = (body.phone as string | undefined) || "";
      return crearCheckoutSuscripcion(body, phone, origin);
    }
    if (kind === "topup") {
      // NO se pasa phone del body intencionalmente.
      return crearCheckoutTopup(body, origin);
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
  body: { plan?: string; embedded?: unknown },
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
  const embedded = body.embedded === true;

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

  // Embedded ("embedded_page" en la API v22 de Stripe): el formulario se
  // monta en /checkout y Stripe redirige a return_url al completar. Hosted
  // (default): success_url/cancel_url como siempre. Misma metadata en ambos →
  // el webhook procesa idéntico.
  const params: Stripe.Checkout.SessionCreateParams = {
    mode: "subscription",
    payment_method_types: ["card"],
    line_items: lineItems,
    metadata: {
      kind: "subscription",
      plan,
      phone,
    },
    phone_number_collection: { enabled: true },
  };
  if (embedded) {
    params.ui_mode = "embedded_page";
    params.return_url = `${origin}/success?session_id={CHECKOUT_SESSION_ID}`;
  } else {
    params.success_url = `${origin}/success?session_id={CHECKOUT_SESSION_ID}`;
    params.cancel_url = `${origin}/cancel`;
  }
  const session = await getStripe().checkout.sessions.create(params);

  if (embedded) {
    if (!session.client_secret) {
      console.error("[CHECKOUT] embedded sin client_secret en la sesión");
      return NextResponse.json({ error: "checkout_failed" }, { status: 502 });
    }
    return NextResponse.json({ clientSecret: session.client_secret });
  }
  return NextResponse.json({ url: session.url });
}


async function crearCheckoutTopup(
  body: { paquete?: string },
  origin: string,
) {
  // 1. Auth obligatorio · top-ups no son flow público.
  const session = await auth();
  if (!session) {
    return NextResponse.json(
      { error: "unauthenticated" },
      { status: 401 },
    );
  }

  // 2. Identidad SOLO server-side (regla T1.4.D #1: nunca aceptar
  //    identificadores del cliente). El stripeCustomerId asocia el pago
  //    al customer existente; el subscriptionId nos sirve para resolver
  //    el teléfono server-side.
  const subscriptionId = (session as { subscriptionId?: string })
    .subscriptionId;
  const customerId = (session as { stripeCustomerId?: string })
    .stripeCustomerId;
  if (!subscriptionId || !customerId) {
    return NextResponse.json(
      { error: "no_subscription_in_session" },
      { status: 403 },
    );
  }

  // 3. Validar paquete contra el catálogo declarativo.
  const paquete = body.paquete;
  if (!paquete || !(paquete in PAQUETES)) {
    return NextResponse.json(
      { error: "invalid_paquete. Use '100', '500' or '2000'." },
      { status: 400 },
    );
  }

  const p = PAQUETES[paquete as PaqueteKey];
  if (!p.priceId) {
    console.error(
      `[CHECKOUT] paquete=${paquete} sin STRIPE_PRICE_PAQUETE_${paquete} configurada`,
    );
    return NextResponse.json(
      { error: "paquete_no_configurado" },
      { status: 503 },
    );
  }

  // 4. Resolver teléfono desde el backend (fuente confiable, T1.4.D
  //    bajo HMAC). Si falla, abortamos: no se permite checkout sin un
  //    teléfono validado para acreditar.
  const userRes = await fetchUsuarioResumen(subscriptionId);
  if (!userRes.ok) {
    console.error(
      `[CHECKOUT] topup no se pudo resolver telefono backend: ${userRes.error ?? "unknown"}`,
    );
    return NextResponse.json(
      { error: "backend_unavailable" },
      { status: 502 },
    );
  }
  const telefono = userRes.data.usuario.telefono;
  if (!telefono) {
    return NextResponse.json(
      { error: "no_phone_in_user_record" },
      { status: 503 },
    );
  }

  // 5. Crear Stripe Checkout. Asociamos al customer existente; el
  //    teléfono que viaja en metadata lo decide el backend, no el cliente.
  const sessionStripe = await getStripe().checkout.sessions.create({
    mode: "payment",
    payment_method_types: ["card"],
    line_items: [{ price: p.priceId, quantity: 1 }],
    customer: customerId,
    success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/cancel`,
    metadata: {
      kind: "topup",
      paquete,
      // creditos canónicos del catálogo · cliente no puede manipularlos.
      creditos: String(p.creditos),
      // telefono resuelto server-side desde el backend · cliente no
      // puede manipularlo aunque mande body.phone arbitrario.
      telefono,
    },
  });

  return NextResponse.json({ url: sessionStripe.url });
}
