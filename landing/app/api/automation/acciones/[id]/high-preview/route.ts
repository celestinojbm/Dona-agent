// landing/app/api/automation/acciones/[id]/high-preview/route.ts
//
// Route handler server-side para el preview dedicado HIGH. Resuelve
// subscriptionId desde auth(), nunca desde el cliente, y delega al bridge
// HMAC interno.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { obtenerPreviewHigh } from "@/lib/automation-bridge";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
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
  const { id } = await ctx.params;
  const accionId = Number.parseInt(id, 10);
  if (!Number.isInteger(accionId) || accionId <= 0) {
    return NextResponse.json({ error: "invalid_accion_id" }, { status: 400 });
  }

  const result = await obtenerPreviewHigh(subscriptionId, accionId);
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }
  if (result.status === 404) {
    return NextResponse.json({ error: "accion_not_found" }, { status: 404 });
  }
  if (result.status === 409) {
    return NextResponse.json(
      { error: "high_confirmation_not_available" },
      { status: 409 },
    );
  }
  if (result.error === "timeout") {
    return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
  }
  return NextResponse.json(
    { error: "backend_unavailable" },
    { status: 502 },
  );
}
