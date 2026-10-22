// landing/app/api/engineering/login/route.ts
// Acceso al panel de ingeniería: valida el token del dueño y lo deja en una
// cookie httpOnly. DELETE cierra la sesión del panel.
//
// El token NUNCA se acepta por query string (quedaría en logs/history del
// browser); solo por body JSON. La validación es timing-safe y fail-closed
// (ver lib/panel-auth.ts).
//
// Cupo: 5 intentos / 15 min por IP+usuario (env RATE_LIMIT_LOGIN_*).
// Al pasarse responde 429 + Retry-After, igual si el token es bueno, malo
// o el panel no está configurado.

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  esTokenPanelValido,
  PANEL_COOKIE,
  PANEL_COOKIE_MAX_AGE,
} from "@/lib/panel-auth";
import { rutaRetiradaEnPausa } from "@/lib/pausa-api";
import { consumirLogin, ipDe } from "@/lib/rate-limit";

function respuestaLimite(retryAfterSegundos: number): NextResponse {
  // Mismo cuerpo siempre: no dice si el token era válido ni si el panel
  // está configurado. El header Retry-After es el único dato operativo.
  return NextResponse.json(
    { error: "rate_limit_excedido" },
    {
      status: 429,
      headers: {
        "Retry-After": String(retryAfterSegundos),
        "Cache-Control": "no-store",
      },
    },
  );
}

export async function POST(req: Request) {
  // Pausa: el panel no existe públicamente (404) y no emite cookies nuevas.
  // Va ANTES del cupo: un 429 delataría que la ruta sigue viva.
  const retirada = rutaRetiradaEnPausa();
  if (retirada) return retirada;

  // Cuenta el intento antes de leer el token. Así el 429 no depende de si
  // el secreto coincide o de si PANEL_INGENIERIA_TOKEN existe.
  const cupo = consumirLogin(ipDe(req));
  if (!cupo.permitido) {
    console.warn(`[PANEL] login rate limit excedido retry=${cupo.retryAfterSegundos}s`);
    return respuestaLimite(cupo.retryAfterSegundos);
  }

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

// DELETE sigue disponible en pausa: solo borra la cookie del panel (no
// consulta APIs ni valida tokens), útil para limpiar sesiones anteriores.
export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.delete(PANEL_COOKIE);
  return NextResponse.json({ ok: true });
}
