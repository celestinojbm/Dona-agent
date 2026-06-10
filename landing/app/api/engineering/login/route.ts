// landing/app/api/engineering/login/route.ts
// Acceso al panel de ingeniería: valida el token del dueño y lo deja en una
// cookie httpOnly. DELETE cierra la sesión del panel.
//
// El token NUNCA se acepta por query string (quedaría en logs/history del
// browser); solo por body JSON. La validación es timing-safe y fail-closed
// (ver lib/panel-auth.ts).

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  esTokenPanelValido,
  PANEL_COOKIE,
  PANEL_COOKIE_MAX_AGE,
} from "@/lib/panel-auth";

export async function POST(req: Request) {
  let token: unknown;
  try {
    const body = (await req.json()) as { token?: unknown };
    token = body?.token;
  } catch {
    return NextResponse.json({ error: "bad_request" }, { status: 400 });
  }

  if (typeof token !== "string" || !esTokenPanelValido(token)) {
    // Respuesta única para token inválido y panel sin configurar: no
    // revelamos cuál de los dos es.
    return NextResponse.json({ error: "invalid_token" }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(PANEL_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: PANEL_COOKIE_MAX_AGE,
  });
  return NextResponse.json({ ok: true });
}

export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.delete(PANEL_COOKIE);
  return NextResponse.json({ ok: true });
}
