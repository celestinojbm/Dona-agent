// landing/lib/rate-limit.ts — Cupo del login del panel de ingeniería.
//
// El tope compartido entre instancias está en el backend
// (agent/rate_limiter.consumir_login): Redis si REDIS_URL conecta, y memoria
// de ese proceso si Redis no está. Este archivo conserva la ventana local
// para cuando el bridge no responde (backend caído o sin configurar). Esa
// memoria es por instancia y no persiste. No usamos el token como clave.
//
// Clave = IP + usuario. El panel tiene un solo principal ("engineering");
// no se toma un usuario del body, porque el cliente podría cambiarlo en
// cada intento y evadir el cupo. La respuesta 429 es siempre la misma: no
// dice si el token era válido ni si el panel está configurado.

import "server-only";

import { consultarCupoLogin } from "@/lib/login-cupo-bridge";

export const USUARIO_PANEL = "engineering";
export const LOGIN_MAX_DEFAULT = 5;
export const LOGIN_VENTANA_SEGUNDOS_DEFAULT = 15 * 60;

const MAX_CUBETAS = 2000;

type ResultadoCupo = {
  permitido: boolean;
  retryAfterSegundos: number;
};

const cubetas = new Map<string, number[]>();
let reloj: () => number = () => Date.now();

/** Reloj inyectable (tests). `null` vuelve a Date.now. */
export function fijarReloj(fn: (() => number) | null): void {
  reloj = fn ?? (() => Date.now());
}

/** Vacía las ventanas de este proceso. */
export function reiniciarCupos(): void {
  cubetas.clear();
}

function enteroEnv(nombre: string, defecto: number): number {
  const raw = process.env[nombre]?.trim() ?? "";
  if (!raw) return defecto;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1) return defecto;
  return n;
}

/** Topes del login. Se leen en cada intento para respetar el entorno. */
export function configLogin(): { maximo: number; ventanaSegundos: number } {
  return {
    maximo: enteroEnv("RATE_LIMIT_LOGIN_MAX", LOGIN_MAX_DEFAULT),
    ventanaSegundos: enteroEnv(
      "RATE_LIMIT_LOGIN_WINDOW_SECONDS",
      LOGIN_VENTANA_SEGUNDOS_DEFAULT,
    ),
  };
}

function primerIp(valor: string | null): string {
  if (!valor) return "";
  return valor.split(",")[0]?.trim() ?? "";
}

function ultimaIp(valor: string | null): string {
  if (!valor) return "";
  const partes = valor
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  return partes[partes.length - 1] ?? "";
}

/**
 * IP del cliente. Prefiere el header que fija la plataforma (no lo puede
 * reescribir el request). Si solo hay X-Forwarded-For, usa el último salto:
 * el primero lo puede poner el cliente.
 */
export function ipDe(req: Request): string {
  const vercel = primerIp(req.headers.get("x-vercel-forwarded-for"));
  const real = primerIp(req.headers.get("x-real-ip"));
  const xff = ultimaIp(req.headers.get("x-forwarded-for"));
  const ip = vercel || real || xff || "desconocida";
  return ip.slice(0, 80).toLowerCase();
}

/** Clave IP+usuario. El usuario vacío cae en un balde propio, no en otro. */
export function claveCupo(ip: string, usuario: string): string {
  const u = usuario.trim().toLowerCase() || "anonimo";
  return `${ip}|${u}`;
}

function podarCubetas(): void {
  if (cubetas.size <= MAX_CUBETAS) return;
  const orden = [...cubetas.entries()].sort((a, b) => {
    const ua = a[1][a[1].length - 1] ?? 0;
    const ub = b[1][b[1].length - 1] ?? 0;
    return ua - ub;
  });
  const sobran = cubetas.size - MAX_CUBETAS;
  for (const [clave] of orden.slice(0, sobran)) cubetas.delete(clave);
}

/**
 * Consume un intento. El rechazo no se anota (no alarga la ventana).
 * `retryAfterSegundos` es 0 cuando el intento entra.
 */
export function consumirCupo(
  clave: string,
  maximo: number,
  ventanaSegundos: number,
): ResultadoCupo {
  if (maximo < 1 || ventanaSegundos <= 0) {
    return { permitido: true, retryAfterSegundos: 0 };
  }
  const ahora = reloj();
  const ventanaMs = ventanaSegundos * 1000;
  const marcas = (cubetas.get(clave) ?? []).filter((t) => ahora - t < ventanaMs);
  if (marcas.length >= maximo) {
    cubetas.set(clave, marcas);
    const viejo = Math.min(...marcas);
    const retry = Math.max(1, Math.ceil((viejo + ventanaMs - ahora) / 1000));
    return { permitido: false, retryAfterSegundos: retry };
  }
  marcas.push(ahora);
  cubetas.set(clave, marcas);
  podarCubetas();
  return { permitido: true, retryAfterSegundos: 0 };
}

/** Cupo local (fallback) para esta IP y el principal fijo. */
export function consumirLogin(ip: string): ResultadoCupo {
  const { maximo, ventanaSegundos } = configLogin();
  return consumirCupo(claveCupo(ip, USUARIO_PANEL), maximo, ventanaSegundos);
}

/**
 * Primero el cupo compartido (Redis en el backend). Si el bridge no contesta,
 * la memoria de esta instancia. Nunca un fallo de red equivale a "permitido"
 * sin contar el intento.
 */
export async function resolverCupoLogin(ip: string): Promise<ResultadoCupo> {
  const remoto = await consultarCupoLogin(ip, USUARIO_PANEL);
  if (remoto) return remoto;
  // El bridge ya registró por qué no hubo respuesta. Contamos aquí para no
  // dejar el intento libre.
  return consumirLogin(ip);
}
