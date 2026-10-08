// landing/lib/app-sesion.ts — Sesión del piloto app-first (J7.5).
//
// Solo cuenta una sesión emitida por el provider "cuenta" (auth.ts). Una
// sesión del dashboard antiguo (Stripe) no abre /app, y viceversa: las rutas
// antiguas exigen subscriptionId, que una sesión "cuenta" no tiene.
import "server-only";

import { auth } from "@/auth";
import { appPilotoHabilitado } from "@/lib/app-piloto";

export interface SesionApp {
  usuarioId: number;
  workspaceId: number;
  email: string;
}

function entero(valor: unknown): number | null {
  return typeof valor === "number" && Number.isInteger(valor) && valor > 0 ? valor : null;
}

export async function sesionApp(): Promise<SesionApp | null> {
  if (!appPilotoHabilitado()) return null;
  const s = (await auth()) as
    | { tipo?: unknown; usuarioId?: unknown; workspaceId?: unknown; user?: { email?: string | null } }
    | null;
  if (!s || s.tipo !== "cuenta") return null;
  const usuarioId = entero(s.usuarioId);
  const workspaceId = entero(s.workspaceId);
  if (!usuarioId || !workspaceId) return null;
  return { usuarioId, workspaceId, email: s.user?.email ?? "" };
}

/** Payload base que identifica al usuario ante /internal/app. */
export function identidad(s: SesionApp): { usuario_id: number; workspace_id: number } {
  return { usuario_id: s.usuarioId, workspace_id: s.workspaceId };
}
