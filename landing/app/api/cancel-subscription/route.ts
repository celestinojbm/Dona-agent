import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { getStripe } from "@/lib/stripe";

// T1.4.F — Cancelación al final del período (no inmediata).
//
// Antes de T1.4.F este handler llamaba a stripe.subscriptions.cancel(id),
// que cancela la suscripción inmediatamente y revoca el acceso. Decisión
// owner: el usuario debe poder usar lo que ya pagó hasta el final del
// período. Ahora hacemos un update con cancel_at_period_end=true:
//
//   - La suscripción queda marcada para no renovar.
//   - Stripe genera customer.subscription.updated (cap=true) inmediatamente
//     y customer.subscription.deleted al final del período.
//   - El backend (T1.3.C _procesar_subscription_deleted) preserva el saldo
//     de créditos del usuario al recibir el deleted final.
//
// El subscriptionId se toma SOLO de la sesión NextAuth server-side (regla
// T1.4.D). NUNCA del request del cliente.

function shortId(id: string): string {
  if (!id) return "***";
  if (id.length <= 12) return "***";
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

export async function POST() {
  const session = await auth();

  if (!session) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const subscriptionId = (session as { subscriptionId?: string })
    .subscriptionId;

  if (!subscriptionId) {
    return NextResponse.json(
      { error: "no_subscription_in_session" },
      { status: 400 },
    );
  }

  try {
    const updated = await getStripe().subscriptions.update(subscriptionId, {
      cancel_at_period_end: true,
    });

    // Extraer fecha de fin de período del primer item (en stripe@22
    // current_period_end vive en items.data[0], no en root).
    const firstItem = updated.items?.data?.[0];
    const periodEnd =
      typeof firstItem?.current_period_end === "number"
        ? firstItem.current_period_end
        : null;

    // Respuesta clara para que el dashboard refresque y la UI muestre
    // el estado nuevo (cancelación pendiente, fecha de corte).
    return NextResponse.json({
      ok: true,
      cancel_at_period_end: Boolean(updated.cancel_at_period_end),
      current_period_end: periodEnd,
      status: updated.status,
      message:
        "Cancelación programada al final del período actual. " +
        "Mantienes acceso hasta esa fecha.",
    });
  } catch (err: unknown) {
    const msg =
      err instanceof Error ? err.message : "Failed to cancel subscription";
    console.error(
      `[CANCEL] update(cancel_at_period_end) falló sub=${shortId(subscriptionId)}: ${msg}`,
    );
    return NextResponse.json(
      { error: "cancel_failed" },
      { status: 500 },
    );
  }
}
