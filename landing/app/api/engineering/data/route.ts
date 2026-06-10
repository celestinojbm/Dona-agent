// landing/app/api/engineering/data/route.ts
// Datos del panel de ingeniería. El cliente (panel-client.tsx) hace polling
// acá cada ~60s.
//
// Reglas:
//   - Solo responde con la cookie del panel válida (token del dueño,
//     comparación timing-safe, fail-closed si falta el env var).
//   - Los tokens de GitHub/Render viven en el bridge server-side; acá solo
//     pasan datos ya transformados.
//   - Sin cache: cada GET pega a las APIs (el polling ya es el throttle).

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { esTokenPanelValido, PANEL_COOKIE } from "@/lib/panel-auth";
import { fetchPanelData } from "@/lib/panel-bridge";

export const dynamic = "force-dynamic";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(PANEL_COOKIE)?.value;
  if (!esTokenPanelValido(token)) {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  const data = await fetchPanelData();
  return NextResponse.json(data, {
    headers: { "Cache-Control": "no-store" },
  });
}
