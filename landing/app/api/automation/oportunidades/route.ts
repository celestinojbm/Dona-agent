// landing/app/api/automation/oportunidades/route.ts
//
// GET · lista oportunidades detectadas para el usuario autenticado.
//
// El subscription_id viene SIEMPRE de auth() server-side (T1.4.D guardrail).
// El backend resuelve telefono · NUNCA aceptamos identificadores del cliente.
//
// Mismo contrato de fallback que /api/automation/acciones: si el backend
// devuelve 404 'subscription_no_persistida' o el JWT viejo no trae
// subscriptionId, retornamos 200 con lista vacía · el componente UI
// muestra empty state. La lista vacía no expone PII ni escala privilegios.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { fetchOportunidades } from "@/lib/automation-bridge";

const EMPTY = { oportunidades: [], count: 0 };

export async function GET() {
  const session = await auth();
  if (!session) {
    console.warn("[OPORTUNIDADES] GET · missing_session");
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) {
    // JWT antiguo sin subscriptionId · no es error fatal, empty state.
    console.warn("[OPORTUNIDADES] GET · missing_subscription_id");
    return NextResponse.json(EMPTY);
  }

  const result = await fetchOportunidades(subscriptionId);
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }

  // Error categorizado · log seguro (sin secrets, sin telefono)
  if (result.status === 404) {
    console.warn(
      "[OPORTUNIDADES] GET · backend_404 subscription_no_persistida · empty fallback",
    );
    return NextResponse.json(EMPTY);
  }
  if (result.status === 401) {
    console.error(
      "[OPORTUNIDADES] GET · backend_401 INTERNAL_BRIDGE_SECRET desincronizado entre Vercel/Render?",
    );
    return NextResponse.json({ error: "backend_auth_error" }, { status: 502 });
  }
  if (result.error === "timeout") {
    console.error("[OPORTUNIDADES] GET · bridge_timeout");
    return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
  }
  if (result.error === "backend_url_missing") {
    console.error("[OPORTUNIDADES] GET · missing_env BACKEND_URL");
  } else if (result.error === "internal_bridge_secret_missing") {
    console.error("[OPORTUNIDADES] GET · missing_env INTERNAL_BRIDGE_SECRET");
  } else {
    console.error(
      `[OPORTUNIDADES] GET · backend_${result.status ?? "unknown"} ${result.error ?? ""}`,
    );
  }
  return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
}
