// landing/app/api/dashboard-data/route.ts
// T1.4.D — Proxy server-side al backend para datos del dashboard.
//
// Devuelve el JSON consolidado que la UI del dashboard (T1.4.E) va a
// renderizar: créditos, plan, suscripción, transacciones recientes.
//
// Reglas críticas:
//   - subscriptionId SOLO viene de la sesión NextAuth server-side (auth()).
//     NUNCA del request del cliente (ni body, ni query, ni headers
//     arbitrarios). Confirmado en revisión del owner sobre T1.4.C: el HMAC
//     protege la transmisión, pero si aceptáramos IDs del browser un
//     usuario logueado podría consultar la sub de otro.
//   - INTERNAL_BRIDGE_SECRET y STRIPE_SECRET_KEY nunca llegan al cliente
//     (solo se usan dentro de fetchUsuarioResumen y getStripe()).
//   - Errores del backend se traducen a un código apropiado para el
//     cliente; nunca se filtra el body crudo del backend al frontend.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import {
  fetchUsuarioResumen,
  type UsuarioResumen,
} from "@/lib/internal-bridge";
import { getStripe } from "@/lib/stripe";
import type Stripe from "stripe";

/** Datos que aporta Stripe SDK que no están cacheados en backend. */
type StripeOverrides = {
  current_period_end: number | null;
  cancel_at_period_end: boolean;
  status_stripe: string | null;
};

const STRIPE_OVERRIDES_DEFAULT: StripeOverrides = {
  current_period_end: null,
  cancel_at_period_end: false,
  status_stripe: null,
};

function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

async function fetchStripeOverrides(
  subscriptionId: string,
): Promise<StripeOverrides> {
  if (!subscriptionId) return STRIPE_OVERRIDES_DEFAULT;
  if (!process.env.STRIPE_SECRET_KEY) {
    // En dev sin Stripe configurado, devolvemos defaults: el dashboard
    // simplemente no muestra fechas ni flag de cancel pendiente.
    return STRIPE_OVERRIDES_DEFAULT;
  }
  try {
    const sub: Stripe.Subscription = await getStripe().subscriptions.retrieve(
      subscriptionId,
    );
    // En stripe@22 current_period_end vive en cada subscription item; el
    // valor relevante es el del primer item (todos coinciden para subs de
    // un solo precio recurrente, que es nuestro caso).
    const firstItem = sub.items?.data?.[0];
    const periodEnd =
      typeof firstItem?.current_period_end === "number"
        ? firstItem.current_period_end
        : null;
    return {
      current_period_end: periodEnd,
      cancel_at_period_end: Boolean(sub.cancel_at_period_end),
      status_stripe: sub.status ?? null,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : "unknown";
    console.error(
      `[DASHBOARD] Stripe retrieve falló sub=${shortId(subscriptionId)}: ${msg}`,
    );
    return STRIPE_OVERRIDES_DEFAULT;
  }
}

export async function GET() {
  // 1. Auth: solo usuarios con sesión válida.
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  // 2. Tomar subscriptionId SOLO de la sesión server-side.
  // Guardrail T1.4.D: NUNCA del request del cliente.
  const subscriptionId = (session as { subscriptionId?: string })
    .subscriptionId;
  const sessionEmail = session.user?.email ?? null;

  if (!subscriptionId) {
    return NextResponse.json(
      { error: "no_subscription_in_session" },
      { status: 403 },
    );
  }

  // 3. Llamar al backend (T1.4.C) en paralelo a Stripe SDK.
  const [backendRes, stripeOverrides] = await Promise.all([
    fetchUsuarioResumen(subscriptionId),
    fetchStripeOverrides(subscriptionId),
  ]);

  // 4. Manejar errores del backend con códigos específicos.
  if (!backendRes.ok) {
    if (backendRes.status === 404) {
      return NextResponse.json(
        { error: "subscription_not_found" },
        { status: 404 },
      );
    }
    if (backendRes.status === 401) {
      // Indica secret desincronizado entre Vercel y Render. Alertable.
      console.error(
        "[DASHBOARD] Backend respondió 401 — INTERNAL_BRIDGE_SECRET desincronizado entre Vercel y Render?",
      );
      return NextResponse.json(
        { error: "backend_auth_error" },
        { status: 502 },
      );
    }
    if (backendRes.error === "timeout") {
      return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
    }
    return NextResponse.json(
      { error: "backend_unavailable" },
      { status: 502 },
    );
  }

  // 5. Merge: datos del backend + Stripe + email de sesión.
  const data: UsuarioResumen = backendRes.data;
  const merged = {
    ...data,
    usuario: {
      ...data.usuario,
      email: sessionEmail,
    },
    suscripcion: {
      ...data.suscripcion,
      current_period_end: stripeOverrides.current_period_end,
      cancel_at_period_end: stripeOverrides.cancel_at_period_end,
    },
  };

  return NextResponse.json(merged);
}
