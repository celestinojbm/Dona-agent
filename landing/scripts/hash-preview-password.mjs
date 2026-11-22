#!/usr/bin/env node
// Genera PREVIEW_LOGIN_PASSWORD_HASH leyendo la contraseña por stdin.
//
// Uso (desde landing/):
//   node scripts/hash-preview-password.mjs
//   (escribe la contraseña y cierra con Ctrl-D)
//
//   printf '%s' 'tu-contraseña' | node scripts/hash-preview-password.mjs
//
// stdout: una sola línea
//   scrypt$16384$8$1$<salt_base64url_16B>$<key_base64url_32B>
//
// Ese valor va en Vercel, alcance Preview (nunca Production):
//   PREVIEW_LOGIN_EMAIL
//   PREVIEW_LOGIN_PASSWORD_HASH
// El bypass solo existe si VERCEL_ENV === "preview".
// La contraseña no se imprime. Se quita un único salto de línea final
// (el de echo); el resto se hashea tal cual.

import { randomBytes, scryptSync } from "node:crypto";
import { readFileSync } from "node:fs";

const N = 16384;
const R = 8;
const P = 1;
const KEY_LEN = 32;
const PASSWORD_MAX = 1024;
const MAXMEM = 64 * 1024 * 1024;

function fallar(mensaje) {
  process.stderr.write(mensaje + "\n");
  process.exit(1);
}

function leerPassword() {
  let raw;
  try {
    raw = readFileSync(0, "utf8");
  } catch {
    fallar("No se pudo leer la contraseña por stdin.");
  }
  if (raw.endsWith("\r\n")) raw = raw.slice(0, -2);
  else if (raw.endsWith("\n")) raw = raw.slice(0, -1);
  if (raw.length === 0) fallar("La contraseña está vacía.");
  if (raw.length > PASSWORD_MAX) fallar("La contraseña supera 1024 caracteres.");
  return raw;
}

const password = leerPassword();
const salt = randomBytes(16);
const key = scryptSync(password, salt, KEY_LEN, { N, r: R, p: P, maxmem: MAXMEM });
process.stdout.write(
  `scrypt$${N}$${R}$${P}$${salt.toString("base64url")}$${key.toString("base64url")}\n`,
);
