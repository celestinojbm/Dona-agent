// landing/app/api/automation/acciones/generar/route.ts
//
// POST · invoca el Opportunity Engine y crea acciones (idempotente).
//
// Hotfix T2.1.B: si la sub no está persistida en suscripcion_stripe,
// devolvemos 404 con error claro · el componente lo muestra como "no
// hay datos suficientes para generar". No es error fatal del sistema.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { generarAcciones } from "@/lib/automation-bridge";

export async function POST() {
  const session = await auth();
  if (!session) {
    console.warn("[ACT-CENTER] POST /generar · missing_session");
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) {
    console.warn("[ACT-CENTER] POST /generar · missing_subscription_id");
    return NextResponse.json(
      { error: "no_subscription_in_session" },
      { status: 403 },
    );
  }
  const result = await generarAcciones(subscriptionId);
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }
  if (result.status === 404) {
    console.warn("[ACT-CENTER] POST /generar · backend_404 subscription_no_persistida");
    return NextResponse.json(
      { error: "subscription_not_persisted" },
      { status: 404 },
    );
  }
  if (result.error === "timeout") {
    console.error("[ACT-CENTER] POST /generar · bridge_timeout");
    return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
  }
  if (result.error === "backend_url_missing") {
    console.error("[ACT-CENTER] POST /generar · missing_env BACKEND_URL");
  } else if (result.error === "internal_bridge_secret_missing") {
    console.error(
      "[ACT-CENTER] POST /generar · missing_env INTERNAL_BRIDGE_SECRET",
    );
  } else {
    console.error(
      `[ACT-CENTER] POST /generar · backend_${result.status ?? "unknown"} ${result.error ?? ""}`,
    );
  }
  return NextResponse.json(
    { error: "backend_unavailable" },
    { status: 502 },
  );
}
