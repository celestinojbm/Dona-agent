// landing/app/api/automation/acciones/generar/route.ts
//
// POST · invoca el Opportunity Engine y crea acciones (idempotente).

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { generarAcciones } from "@/lib/automation-bridge";

export async function POST() {
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
  const result = await generarAcciones(subscriptionId);
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
    return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
  }
  return NextResponse.json(
    { error: "backend_unavailable" },
    { status: 502 },
  );
}
