// landing/lib/preview-login.ts — Acceso del dueño en previews de Vercel.
//
// En producción el login sigue siendo el de Stripe (password derivado
// "dona-" + hex). Este módulo solo corre si VERCEL_ENV es exactamente
// "preview" y existen PREVIEW_LOGIN_EMAIL y PREVIEW_LOGIN_PASSWORD_HASH.
// El hash es scrypt; la contraseña en claro no se guarda ni se escribe
// en logs. Si falta algo o el hash no parsea, el bypass no existe y
// authorize sigue el flujo normal.

import {
  createHmac,
  randomBytes,
  scrypt,
  scryptSync,
  timingSafeEqual,
  type ScryptOptions,
} from "node:crypto";

import type { UsuarioResumen } from "@/lib/dashboard-types";

function scryptAsync(
  password: string,
  salt: Buffer,
  keylen: number,
  options: ScryptOptions,
): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scrypt(password, salt, keylen, options, (err, derived) => {
      if (err) reject(err);
      else resolve(derived);
    });
  });
}

/** Parámetros fijos. El parser rechaza cualquier otro N/r/p (evita un N enorme en la env). */
export const PREVIEW_SCRYPT_N = 16384;
export const PREVIEW_SCRYPT_R = 8;
export const PREVIEW_SCRYPT_P = 1;
const KEY_LEN = 32;
const SALT_LEN = 16;
const PASSWORD_MAX = 1024;
const MAXMEM = 64 * 1024 * 1024;

const SCRYPT_OPTS = {
  N: PREVIEW_SCRYPT_N,
  r: PREVIEW_SCRYPT_R,
  p: PREVIEW_SCRYPT_P,
  maxmem: MAXMEM,
} as const;

/**
 * Formato (una línea, sin espacios):
 *   scrypt$16384$8$1$<salt_base64url>$<key_base64url>
 * salt = 16 bytes, key = 32 bytes, base64url sin padding.
 */
const HASH_RE =
  /^scrypt\$16384\$8\$1\$([A-Za-z0-9_-]{22})\$([A-Za-z0-9_-]{43})$/;

export type UsuarioPreview = {
  id: "preview-owner";
  email: string;
  name: string;
  plan: "preview";
  preview: true;
};

type HashParseado = { salt: Buffer; key: Buffer };

export function parsearHashPreview(hash: string): HashParseado | null {
  if (typeof hash !== "string") return null;
  const m = HASH_RE.exec(hash.trim());
  if (!m) return null;
  const salt = Buffer.from(m[1], "base64url");
  const key = Buffer.from(m[2], "base64url");
  if (salt.length !== SALT_LEN || key.length !== KEY_LEN) return null;
  return { salt, key };
}

/** Genera el valor de PREVIEW_LOGIN_PASSWORD_HASH. No imprime la contraseña. */
export function crearHashPreview(password: string): string {
  if (typeof password !== "string" || password.length === 0 || password.length > PASSWORD_MAX) {
    throw new Error("contraseña vacía o demasiado larga");
  }
  const salt = randomBytes(SALT_LEN);
  const key = scryptSync(password, salt, KEY_LEN, SCRYPT_OPTS);
  const params = `${PREVIEW_SCRYPT_N}$${PREVIEW_SCRYPT_R}$${PREVIEW_SCRYPT_P}`;
  return `scrypt$${params}$${salt.toString("base64url")}$${key.toString("base64url")}`;
}

function igualesEnTiempoConstante(a: string, b: string): boolean {
  try {
    const ha = createHmac("sha256", "dona-preview-login-email").update(a, "utf8").digest();
    const hb = createHmac("sha256", "dona-preview-login-email").update(b, "utf8").digest();
    return timingSafeEqual(ha, hb);
  } catch {
    return false;
  }
}

function normalizarEmail(email: string): string {
  return email.trim().toLowerCase();
}

async function passwordCoincide(password: string, parsed: HashParseado): Promise<boolean> {
  try {
    const derivado = await scryptAsync(password, parsed.salt, KEY_LEN, SCRYPT_OPTS);
    if (derivado.length !== parsed.key.length) return false;
    return timingSafeEqual(derivado, parsed.key);
  } catch {
    return false;
  }
}

/**
 * Devuelve el usuario de preview si el bypass está armado y las
 * credenciales coinciden. En cualquier otro caso devuelve null sin
 * tocar Stripe. Con el bypass armado siempre calcula scrypt, aunque el
 * correo no coincida, para no filtrar el correo por tiempo.
 */
export async function autenticarPreview(
  email: unknown,
  password: unknown,
): Promise<UsuarioPreview | null> {
  if (process.env.VERCEL_ENV !== "preview") return null;

  const emailEsperado = normalizarEmail(process.env.PREVIEW_LOGIN_EMAIL ?? "");
  const hash = process.env.PREVIEW_LOGIN_PASSWORD_HASH?.trim() ?? "";
  if (!emailEsperado || !hash) return null;

  const parsed = parsearHashPreview(hash);
  if (!parsed) {
    console.warn(
      "[AUTH] bypass de preview inactivo: PREVIEW_LOGIN_PASSWORD_HASH no tiene formato scrypt",
    );
    return null;
  }

  if (typeof email !== "string" || typeof password !== "string") return null;
  if (password.length === 0 || password.length > PASSWORD_MAX) return null;

  const emailOk = igualesEnTiempoConstante(normalizarEmail(email), emailEsperado);
  const passwordOk = await passwordCoincide(password, parsed);
  if (!emailOk || !passwordOk) return null;

  return {
    id: "preview-owner",
    email: emailEsperado,
    name: emailEsperado,
    plan: "preview",
    preview: true,
  };
}

/**
 * Payload de /api/dashboard-data para la sesión de preview.
 * Ceros y listas vacías: no hay customer ni suscripción de Stripe.
 */
export function datosMinimosPreview(email: string | null): UsuarioResumen {
  return {
    usuario: {
      id: "preview-owner",
      email,
      telefono: "",
    },
    creditos: {
      saldo_actual: 0,
      creditos_mensuales: 0,
      ultimo_movimiento: null,
    },
    suscripcion: {
      estado: "preview",
      plan: "preview",
      stripe_customer_id: "",
      stripe_subscription_id: "",
      current_period_end: null,
      cancel_at_period_end: false,
      actualizado: null,
    },
    transacciones_recientes: [],
    resumen: {
      puede_cancelar: false,
      dashboard_ready: true,
    },
  };
}
