// landing/app/api/automation/acciones/[id]/high-confirmar/route.ts
//
// Route handler server-side para materializar una accion HIGH ya aprobada.
// Exige que el cliente mande confirmacion literal; subscriptionId se toma
// de auth() y el backend vuelve a validar ownership/tipo/estado.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { confirmarHighDedicado } from "@/lib/automation-bridge";

export async function POST(
  req: Request,
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

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "json_invalid" }, { status: 400 });
  }
  const confirmacion =
    typeof body === "object" && body !== null && "confirmacion" in body
      ? (body as { confirmacion?: unknown }).confirmacion
      : undefined;
  if (typeof confirmacion !== "string" || confirmacion !== "ENVIAR") {
    return NextResponse.json({ error: "confirmacion_invalida" }, { status: 400 });
  }

  const result = await confirmarHighDedicado(
    subscriptionId,
    accionId,
    confirmacion,
  );
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
