// landing/app/api/automation/acciones/route.ts
//
// GET  · lista acciones del usuario autenticado
// POST · genera acciones (ruta /generar manejada por archivo separado)
//
// El subscription_id viene SIEMPRE de auth() server-side (T1.4.D guardrail).
// El backend resuelve telefono · NUNCA aceptamos identificadores del cliente.
//
// Hotfix T2.1.B: si el backend devuelve 404 'subscription_no_persistida'
// (sub pre-T2.0.B no migrada a suscripcion_stripe) o 'no_subscription_in_session'
// (JWT viejo sin subscriptionId), retornamos 200 con lista vacía. El usuario
// simplemente no tiene acciones aún · el componente UI muestra empty state.
// Esto NO genera riesgo de seguridad: la sesión ya está autenticada, el
// backend no expone PII, y la lista vacía no escala privilegios.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { fetchAcciones } from "@/lib/automation-bridge";

const EMPTY = { acciones: [], count: 0 };

export async function GET(req: Request) {
  const session = await auth();
  if (!session) {
    console.warn("[ACT-CENTER] GET /acciones · missing_session");
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) {
    // JWT antiguo sin subscriptionId · no hay forma de listar acciones,
    // pero tampoco es un error fatal. El componente muestra empty.
    console.warn("[ACT-CENTER] GET /acciones · missing_subscription_id");
    return NextResponse.json(EMPTY);
  }

  const url = new URL(req.url);
  const estado = url.searchParams.get("estado") ?? undefined;

  const result = await fetchAcciones(subscriptionId, estado);
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }

  // Error categorizado · log seguro (sin secrets, sin telefono)
  if (result.status === 404) {
    console.warn(
      "[ACT-CENTER] GET /acciones · backend_404 subscription_no_persistida · empty fallback",
    );
    return NextResponse.json(EMPTY);
  }
  if (result.status === 401) {
    console.error(
      "[ACT-CENTER] GET /acciones · backend_401 INTERNAL_BRIDGE_SECRET desincronizado entre Vercel/Render?",
    );
    return NextResponse.json(
      { error: "backend_auth_error" },
      { status: 502 },
    );
  }
  if (result.error === "timeout") {
    console.error("[ACT-CENTER] GET /acciones · bridge_timeout");
    return NextResponse.json(
      { error: "backend_timeout" },
      { status: 504 },
    );
  }
  if (result.error === "backend_url_missing") {
    console.error(
      "[ACT-CENTER] GET /acciones · missing_env BACKEND_URL",
    );
  } else if (result.error === "internal_bridge_secret_missing") {
    console.error(
      "[ACT-CENTER] GET /acciones · missing_env INTERNAL_BRIDGE_SECRET",
    );
  } else {
    console.error(
      `[ACT-CENTER] GET /acciones · backend_${result.status ?? "unknown"} ${result.error ?? ""}`,
    );
  }
  return NextResponse.json(
    { error: "backend_unavailable" },
    { status: 502 },
  );
}
