// landing/app/api/automation/acciones/[id]/route.ts
//
// GET · lectura canónica de UNA acción + página de su bitácora de audit.
//
// El subscriptionId sale SIEMPRE de auth() server-side (T1.4.D). Cualquier
// identificador que mande el navegador en query/headers se ignora: solo se
// leen el id de la ruta y el cursor/límite de eventos.
//
//   ?eventos_antes_de=<id>  · cursor de la página anterior de eventos
//   ?eventos_limite=<n>     · 1..50 (el backend vuelve a acotarlo)
//
// Respuestas de error (mismo vocabulario que el resto de /acciones/[id]):
//   400 invalid_accion_id · invalid_eventos_cursor · invalid_eventos_limite
//   401 unauthenticated
//   403 no_subscription_in_session
//   404 accion_not_found     (inexistente, de otra suscripción o sub no
//                             persistida · indistinguibles a propósito)
//   502 backend_unavailable  (incluye respuesta incoherente del backend)
//   504 backend_timeout

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { fetchDetalleAccion } from "@/lib/automation-bridge";

const EVENTOS_LIMITE_MAX = 50;
const SIN_CACHE = { "Cache-Control": "no-store" };

// Solo dígitos: parseInt("12abc") daría 12 y abriría la acción equivocada.
function enteroPositivo(valor: string | null): number | null {
  if (valor === null || !/^\d{1,12}$/.test(valor)) return null;
  const n = Number(valor);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

function error(codigo: string, status: number) {
  return NextResponse.json({ error: codigo }, { status, headers: SIN_CACHE });
}

export async function GET(
  req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session) return error("unauthenticated", 401);
  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) return error("no_subscription_in_session", 403);

  const { id } = await ctx.params;
  const accionId = enteroPositivo(id);
  if (accionId === null) return error("invalid_accion_id", 400);

  const url = new URL(req.url);
  const cursorRaw = url.searchParams.get("eventos_antes_de");
  const limiteRaw = url.searchParams.get("eventos_limite");
  const antesDe = cursorRaw === null ? undefined : enteroPositivo(cursorRaw);
  if (antesDe === null) return error("invalid_eventos_cursor", 400);
  const limite = limiteRaw === null ? undefined : enteroPositivo(limiteRaw);
  if (limite === null || (limite !== undefined && limite > EVENTOS_LIMITE_MAX)) {
    return error("invalid_eventos_limite", 400);
  }

  const result = await fetchDetalleAccion(subscriptionId, accionId, {
    antesDe,
    limite,
  });
  if (result.ok && result.data) {
    // El backend filtra por owner; si aun así devolviera otra acción, no
    // se muestra nada antes que mostrar datos ajenos.
    if (result.data.accion?.id !== accionId || !Array.isArray(result.data.eventos)) {
      console.error("[ACT-CENTER] GET /acciones/:id · respuesta incoherente del backend");
      return error("backend_unavailable", 502);
    }
    return NextResponse.json(result.data, { headers: SIN_CACHE });
  }
  if (result.status === 404) return error("accion_not_found", 404);
  if (result.error === "timeout") return error("backend_timeout", 504);
  console.error(
    `[ACT-CENTER] GET /acciones/:id · backend_${result.status ?? "unknown"} ${result.error ?? ""}`,
  );
  return error("backend_unavailable", 502);
}
