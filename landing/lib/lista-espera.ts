// landing/lib/lista-espera.ts — Validación y respuestas de la lista de espera.
//
// Compartido por /api/lista-espera y /api/lista-espera/invitacion. Las rutas
// siguen abiertas durante la pausa a propósito: no venden, no cobran ni dan
// acceso; solo guardan un correo (y, con código válido, lo marcan invitado).

import { BlockList, isIP } from "node:net";

import { NextResponse } from "next/server";
import type { ResultadoListaEspera } from "@/lib/lista-espera-bridge";

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}$/;
const MAX_BODY = 2_000;

export function emailValido(email: unknown): email is string {
  return typeof email === "string" && email.trim().length <= 254 && EMAIL_RE.test(email.trim());
}

// Rangos publicados de Cloudflare (https://www.cloudflare.com/ips-v4 y
// /ips-v6, revisados el 2026-11-23). Cambian muy rara vez; si Cloudflare añade
// uno, el peor caso es que esas visitas compartan el límite de la IP de borde.
const CLOUDFLARE_V4 = [
  "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
  "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
  "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
  "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
];
const CLOUDFLARE_V6 = [
  "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
  "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
];
const cloudflare = new BlockList();
for (const red of CLOUDFLARE_V4) {
  const [base, prefijo] = red.split("/");
  cloudflare.addSubnet(base, Number(prefijo), "ipv4");
}
for (const red of CLOUDFLARE_V6) {
  const [base, prefijo] = red.split("/");
  cloudflare.addSubnet(base, Number(prefijo), "ipv6");
}

function esDeCloudflare(ip: string): boolean {
  const tipo = isIP(ip);
  if (tipo === 0) return false;
  return cloudflare.check(ip, tipo === 4 ? "ipv4" : "ipv6");
}

/**
 * IP del visitante para los límites por IP del backend.
 *
 * `x-real-ip` / `x-forwarded-for` los pone Vercel con la IP que le conecta
 * (pisa lo que mande el cliente). usadona.com va detrás de Cloudflare, así que
 * esa IP es la del borde de Cloudflare, compartida por miles de visitantes:
 * usarla convertiría el límite por IP en un límite casi global.
 *
 * Por eso: si quien conecta a Vercel es Cloudflare, se usa `cf-connecting-ip`
 * (Cloudflare lo sobrescribe siempre). Si no, se ignora: quien entra directo a
 * *.vercel.app podría inventarlo. Vacía si no hay IP válida: el backend la
 * trata como un cubo compartido.
 */
export function ipCliente(req: Request): string {
  const real = req.headers.get("x-real-ip")?.trim();
  const reenviada = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const conectada = real || reenviada || "";
  let ip = conectada;
  if (esDeCloudflare(conectada)) {
    const visitante = req.headers.get("cf-connecting-ip")?.trim() ?? "";
    if (isIP(visitante) !== 0) ip = visitante;
  }
  return ip.length <= 64 ? ip : "";
}

/** Lee el JSON del cuerpo con tope de tamaño. null si no es un objeto. */
export async function leerCuerpo(req: Request): Promise<Record<string, unknown> | null> {
  if (!(req.headers.get("content-type") ?? "").includes("application/json")) return null;
  const texto = await req.text();
  if (texto.length > MAX_BODY) return null;
  try {
    const datos: unknown = JSON.parse(texto);
    return datos && typeof datos === "object" && !Array.isArray(datos)
      ? (datos as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function respuesta(cuerpo: Record<string, unknown>, status: number): NextResponse {
  return NextResponse.json(cuerpo, { status, headers: { "Cache-Control": "no-store" } });
}

/** Traduce el resultado del bridge a una respuesta sin detalles internos. */
export function respuestaDesdeBridge(r: ResultadoListaEspera): NextResponse {
  if (r.ok) return respuesta({ ok: true, estado: r.estado }, 200);
  if (r.status === 400) return respuesta({ ok: false, error: "email_invalido" }, 400);
  if (r.status === 403) return respuesta({ ok: false, error: "codigo_invalido" }, 403);
  if (r.status === 429) return respuesta({ ok: false, error: "demasiados_intentos" }, 429);
  return respuesta({ ok: false, error: "no_disponible" }, 503);
}
