// landing/app/api/automation/acciones/route.ts
//
// GET  · lista acciones del usuario autenticado
// POST · genera acciones (ruta /generar manejada por archivo separado)
//
// El subscription_id viene SIEMPRE de auth() server-side (T1.4.D guardrail).
// El backend resuelve telefono · NUNCA aceptamos identificadores del cliente.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { fetchAcciones } from "@/lib/automation-bridge";

export async function GET(req: Request) {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }
  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) {
    return NextResponse.json(
      { error: "no_subscription_in_session" },
      { status: 403 },
    );
  }

  const url = new URL(req.url);
  const estado = url.searchParams.get("estado") ?? undefined;

  const result = await fetchAcciones(subscriptionId, estado);
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }
  if (result.status === 404) {
    return NextResponse.json(
      { error: "subscription_not_found" },
      { status: 404 },
    );
  }
  if (result.error === "timeout") {
    return NextResponse.json(
      { error: "backend_timeout" },
      { status: 504 },
    );
  }
  return NextResponse.json(
    { error: "backend_unavailable" },
    { status: 502 },
  );
}
