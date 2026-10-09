// landing/lib/lista-espera.ts — Lista de espera "avísame cuando haya plazas".
//
// Validación y guardado server-side de la lista de espera de usadona.com.
// Funciona con la pausa activa: no toca Stripe, el backend ni la sesión.
// Guarda en la tabla public.waitlist_signups del proyecto Supabase "Dona"
// vía la API REST de Supabase con una credencial SOLO de servidor:
//
//   SUPABASE_URL                URL del proyecto (https://<ref>.supabase.co)
//   SUPABASE_SERVICE_ROLE_KEY   clave secreta (service_role o sb_secret_…)
//
// Las dos viven en las env de Vercel (Production). Nunca NEXT_PUBLIC_*.
// La tabla tiene RLS activo sin políticas: anon/authenticated no la leen
// ni escriben. SQL: docs/transition/dona-app-first/waitlist_signups.sql.

import "server-only";

export const FUENTE_LISTA_ESPERA = "usadona-pausa" as const;

/** Tamaño máximo aceptado del cuerpo JSON (bytes). */
export const MAX_CUERPO = 2048;
const MAX_EMAIL = 254;
const MAX_TELEFONO_CRUDO = 32;

// Validación pragmática: local@dominio.tld, sin espacios.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function normalizarEmail(valor: unknown): string | null {
  if (typeof valor !== "string") return null;
  const email = valor.trim().toLowerCase();
  if (email.length === 0 || email.length > MAX_EMAIL) return null;
  return EMAIL_RE.test(email) ? email : null;
}

/**
 * Teléfono opcional en formato internacional. Quita espacios, guiones,
 * puntos y paréntesis; admite un "+" inicial y 7–15 dígitos.
 *   undefined → no se envió (o vacío) · null → inválido · string → normalizado
 */
export function normalizarTelefono(valor: unknown): string | undefined | null {
  if (valor === undefined || valor === null) return undefined;
  if (typeof valor !== "string") return null;
  if (valor.length > MAX_TELEFONO_CRUDO) return null;
  const limpio = valor.trim().replace(/[\s\-().]/g, "");
  if (limpio.length === 0) return undefined;
  return /^\+?[0-9]{7,15}$/.test(limpio) ? limpio : null;
}

export interface Registro {
  email: string;
  phone?: string;
}

export type ResultadoGuardado = "ok" | "sin_configuracion" | "error";

/**
 * Upsert idempotente por email. Si el email ya existe, no falla; si llega
 * con teléfono, actualiza el teléfono (si no llega, conserva el anterior).
 */
export async function guardarEnListaDeEspera(registro: Registro): Promise<ResultadoGuardado> {
  const url = process.env.SUPABASE_URL;
  const clave = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !clave) return "sin_configuracion";

  const fila: Record<string, string> = {
    email: registro.email,
    source: FUENTE_LISTA_ESPERA,
  };
  if (registro.phone) fila.phone = registro.phone;

  const headers: Record<string, string> = {
    apikey: clave,
    "Content-Type": "application/json",
    Prefer: "resolution=merge-duplicates,return=minimal",
  };
  // Claves JWT antiguas (service_role) van también como Bearer; las nuevas
  // sb_secret_… solo en apikey.
  if (clave.startsWith("eyJ")) headers.Authorization = `Bearer ${clave}`;

  try {
    const res = await fetch(
      `${url.replace(/\/+$/, "")}/rest/v1/waitlist_signups?on_conflict=email`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(fila),
        cache: "no-store",
        signal: AbortSignal.timeout(8000),
      },
    );
    return res.ok ? "ok" : "error";
  } catch {
    return "error";
  }
}
