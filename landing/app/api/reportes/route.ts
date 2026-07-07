// landing/app/api/reportes/route.ts
//
// GET · devuelve los números de negocio (Reportes/Medición) del usuario
// autenticado: ventas, gastos, utilidad, pedidos, top categorías.
//
// El subscription_id viene SIEMPRE de auth() server-side (T1.4.D guardrail).
// El backend resuelve telefono · NUNCA aceptamos identificadores del cliente.
//
// Mismo contrato de fallback que /api/assets: si el backend devuelve 404
// 'subscription_no_persistida' o el JWT viejo no trae subscriptionId,
// retornamos 200 con un reporte vacío · el componente UI muestra empty state.
// El reporte vacío no expone PII ni escala privilegios.

import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { fetchReportes } from "@/lib/reportes-bridge";
import type { PeriodoReporte, ReportesResponse } from "@/lib/reportes-types";

const PERIODOS_VALIDOS: readonly PeriodoReporte[] = ["mes", "semana"];

// Reporte vacío para el empty state · no depende del backend. Sirve tanto
// cuando el JWT viejo no trae subscriptionId como cuando la sub aún no está
// persistida (404). El frontend detecta hay_datos=false y muestra su gracia.
function reporteVacio(periodo: PeriodoReporte): ReportesResponse {
  return {
    reporte: {
      periodo,
      etiqueta: "",
      inicio: "",
      fin: "",
      ventas: 0,
      gastos: 0,
      utilidad: 0,
      num_pedidos: 0,
      num_transacciones: 0,
      top_categorias: [],
      comparacion_semana_previa: null,
      hay_datos: false,
    },
  };
}

export async function GET(req: Request) {
  const session = await auth();
  if (!session) {
    console.warn("[REPORTES] GET · missing_session");
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const url = new URL(req.url);
  const periodoRaw = url.searchParams.get("periodo");
  const periodo: PeriodoReporte = PERIODOS_VALIDOS.includes(
    periodoRaw as PeriodoReporte,
  )
    ? (periodoRaw as PeriodoReporte)
    : "mes";

  const subscriptionId = (session as { subscriptionId?: string }).subscriptionId;
  if (!subscriptionId) {
    // JWT antiguo sin subscriptionId · no es error fatal, empty state.
    console.warn("[REPORTES] GET · missing_subscription_id");
    return NextResponse.json(reporteVacio(periodo));
  }

  const result = await fetchReportes(subscriptionId, { periodo });
  if (result.ok && result.data) {
    return NextResponse.json(result.data);
  }

  // Error categorizado · log seguro (sin secrets, sin telefono)
  if (result.status === 404) {
    console.warn(
      "[REPORTES] GET · backend_404 subscription_no_persistida · empty fallback",
    );
    return NextResponse.json(reporteVacio(periodo));
  }
  if (result.status === 401) {
    console.error(
      "[REPORTES] GET · backend_401 INTERNAL_BRIDGE_SECRET desincronizado entre Vercel/Render?",
    );
    return NextResponse.json({ error: "backend_auth_error" }, { status: 502 });
  }
  if (result.error === "timeout") {
    console.error("[REPORTES] GET · bridge_timeout");
    return NextResponse.json({ error: "backend_timeout" }, { status: 504 });
  }
  if (result.error === "backend_url_missing") {
    console.error("[REPORTES] GET · missing_env BACKEND_URL");
  } else if (result.error === "internal_bridge_secret_missing") {
    console.error("[REPORTES] GET · missing_env INTERNAL_BRIDGE_SECRET");
  } else {
    console.error(
      `[REPORTES] GET · backend_${result.status ?? "unknown"} ${result.error ?? ""}`,
    );
  }
  return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
}
