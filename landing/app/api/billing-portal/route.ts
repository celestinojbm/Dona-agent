// landing/app/api/billing-portal/route.ts
// T1.5 — Stripe Customer Portal session generator.
//
// El Customer Portal de Stripe es la fuente canónica para que el usuario
// gestione facturación: cambiar método de pago, descargar facturas,
// pausar/cancelar/reactivar la suscripción, ver historial. En vez de
// reimplementar cada flow, generamos una session firmada del portal y
// redirigimos al usuario allí. Stripe se encarga del resto.
//
// Reglas:
//   - server-only handler. customerId viene SOLO de la sesión NextAuth
//     (regla T1.4.D #1: nunca aceptar identificadores desde el browser).
//   - return_url apunta a /dashboard del mismo origen (o
//     STRIPE_PORTAL_RETURN_URL si está configurada).
//   - Si el portal no está configurado en Stripe Dashboard, Stripe
//     responde "No configuration provided"; lo traducimos a 503 con
//     código 'portal_not_configured' para que el cliente muestre un
//     mensaje útil en vez de un 500 genérico.
//
// Externamente requerido (NO se hace desde código):
//   - Stripe Dashboard → Settings → Customer portal: configurar y
//     activar. Habilitar al menos: "Cancel subscriptions", "Update
//     payment methods", "View invoices".
//   - (Opcional) STRIPE_PORTAL_RETURN_URL en Vercel si se quiere
//     forzar un return_url distinto al origen del request.

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { auth } from "@/auth";
import { getStripe } from "@/lib/stripe";

function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function resolveReturnUrl(req: NextRequest): string {
  const fromEnv = process.env.STRIPE_PORTAL_RETURN_URL?.trim();
  if (fromEnv) return fromEnv;
  const origin = req.headers.get("origin") || "";
  if (origin) return `${origin}/dashboard`;
  // Fallback hardcoded al dominio operativo. Solo se usa si tanto la
  // env var como el header origin faltan, lo que en práctica no ocurre
  // en el flujo normal (NextAuth siempre setea origin).
  return "https://www.usadona.com/dashboard";
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  // customerId desde la sesión server-side. NUNCA del request del cliente.
  const customerId = (session as { stripeCustomerId?: string })
    .stripeCustomerId;
  if (!customerId) {
    return NextResponse.json(
      { error: "no_customer_in_session" },
      { status: 403 },
    );
  }

  const returnUrl = resolveReturnUrl(req);

  try {
    const portal = await getStripe().billingPortal.sessions.create({
      customer: customerId,
      return_url: returnUrl,
    });
    return NextResponse.json({ url: portal.url });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(
      `[BILLING-PORTAL] create session falló cus=${shortId(customerId)}: ${msg}`,
    );

    // Stripe devuelve un mensaje específico cuando el portal no está
    // configurado en el dashboard. Mapearlo a 503 para que la UI muestre
    // un copy útil en vez de un "algo salió mal" genérico.
    const isPortalNotConfigured =
      typeof msg === "string" &&
      (msg.includes("No configuration provided") ||
        msg.includes("default configuration has not been created"));
    if (isPortalNotConfigured) {
      return NextResponse.json(
        { error: "portal_not_configured" },
        { status: 503 },
      );
    }

    return NextResponse.json(
      { error: "portal_create_failed" },
      { status: 500 },
    );
  }
}
