// landing/lib/preview-login.test.ts — Bypass del dueño solo en preview.
//
// El hash lo emite el script (stdin → stdout) y lo verifica el mismo
// parser que usa authorize. Sin VERCEL_ENV=preview el bypass no existe,
// aunque las dos variables estén definidas.

import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  autenticarPreview,
  crearHashPreview,
  datosMinimosPreview,
  parsearHashPreview,
} from "./preview-login";

const SCRIPT = join(
  dirname(fileURLToPath(import.meta.url)),
  "../scripts/hash-preview-password.mjs",
);

const CLAVE = "clave con espacios y ñ";

function hashDelScript(password: string): { status: number | null; stdout: string; stderr: string } {
  const res = spawnSync(process.execPath, [SCRIPT], {
    input: password,
    encoding: "utf8",
  });
  return { status: res.status, stdout: res.stdout ?? "", stderr: res.stderr ?? "" };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("script hash-preview-password", () => {
  it("imprime solo el hash scrypt y no la contraseña", async () => {
    const { autenticarPreview: verificar } = await import("./preview-login");
    const corrida = hashDelScript(CLAVE + "\n");
    expect(corrida.status).toBe(0);
    expect(corrida.stderr).toBe("");
    const hash = corrida.stdout.trim();
    expect(corrida.stdout).toBe(hash + "\n");
    expect(hash).toMatch(/^scrypt\$16384\$8\$1\$[A-Za-z0-9_-]{22}\$[A-Za-z0-9_-]{43}$/);
    expect(hash).not.toContain(CLAVE);
    expect(corrida.stderr).not.toContain(CLAVE);

    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("PREVIEW_LOGIN_EMAIL", "dueno@example.com");
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", hash);
    expect(await verificar("dueno@example.com", CLAVE)).toMatchObject({ preview: true });
    expect(await verificar("dueno@example.com", CLAVE + "x")).toBeNull();
  });

  it("dos corridas generan sales distintos y ambos validan", async () => {
    const a = hashDelScript("misma-clave\n");
    const b = hashDelScript("misma-clave\n");
    expect(a.status).toBe(0);
    expect(b.status).toBe(0);
    expect(a.stdout.trim()).not.toBe(b.stdout.trim());

    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("PREVIEW_LOGIN_EMAIL", "dueno@example.com");
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", a.stdout.trim());
    expect(await autenticarPreview("dueno@example.com", "misma-clave")).not.toBeNull();
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", b.stdout.trim());
    expect(await autenticarPreview("dueno@example.com", "misma-clave")).not.toBeNull();
  });

  it("rechaza contraseña vacía sin imprimir un hash", () => {
    const vacia = hashDelScript("\n");
    expect(vacia.status).toBe(1);
    expect(vacia.stdout).toBe("");
    expect(vacia.stderr).toMatch(/vacía/);

    const soloEof = hashDelScript("");
    expect(soloEof.status).toBe(1);
    expect(soloEof.stdout).toBe("");
  });
});

describe("parsearHashPreview", () => {
  it("acepta el formato fijo y rechaza otro N, bcrypt o basura", () => {
    const bueno = crearHashPreview("abc");
    const partes = bueno.split("$");
    const salt = partes[4] ?? "";
    const key = partes[5] ?? "";
    expect(parsearHashPreview(bueno)).not.toBeNull();
    expect(parsearHashPreview(`  ${bueno}  `)).not.toBeNull();
    expect(parsearHashPreview(`scrypt$1048576$8$1$${salt}$${key}`)).toBeNull();
    expect(parsearHashPreview("bcrypt$2b$12$abcdefghijklmnop")).toBeNull();
    expect(parsearHashPreview("")).toBeNull();
    expect(parsearHashPreview(bueno.replace("$", "$ "))).toBeNull();
  });
});

describe("autenticarPreview", () => {
  const email = "Dueno@Example.com";
  const password = "clave-preview-7f3a9c";
  let hash = "";

  beforeAll(() => {
    hash = crearHashPreview(password);
  });

  function armar(env: string) {
    vi.stubEnv("VERCEL_ENV", env);
    vi.stubEnv("PREVIEW_LOGIN_EMAIL", `  ${email}  `);
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", hash);
  }

  it.each(["production", "development", "", "Preview", "preview "])(
    "no existe cuando VERCEL_ENV=%j",
    async (env) => {
      armar(env);
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
      const res = await autenticarPreview(email, password);
      expect(res).toBeNull();
      const texto = warn.mock.calls.flat().join(" ");
      expect(texto).not.toContain(password);
      expect(texto).not.toContain(hash);
    },
  );

  it("entra en preview con el correo en cualquier capitalización", async () => {
    armar("preview");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const res = await autenticarPreview("  dueno@example.com ", password);
    expect(res).toEqual({
      id: "preview-owner",
      email: "dueno@example.com",
      name: "dueno@example.com",
      plan: "preview",
      preview: true,
    });
    expect(res).not.toHaveProperty("stripeCustomerId");
    expect(res).not.toHaveProperty("subscriptionId");
    const texto = [...warn.mock.calls, ...log.mock.calls].flat().join(" ");
    expect(texto).not.toContain(password);
    expect(texto).not.toContain(hash);
  });

  it("rechaza correo o contraseña distintos sin devolver datos de Stripe", async () => {
    armar("preview");
    expect(await autenticarPreview("otro@example.com", password)).toBeNull();
    expect(await autenticarPreview(email, "otra-clave")).toBeNull();
  });

  it("no existe si falta una variable, aunque VERCEL_ENV sea preview", async () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("PREVIEW_LOGIN_EMAIL", email);
    expect(await autenticarPreview(email, password)).toBeNull();

    vi.stubEnv("PREVIEW_LOGIN_EMAIL", "");
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", crearHashPreview(password));
    expect(await autenticarPreview(email, password)).toBeNull();
  });

  it("un hash mal formado deja el bypass inactivo y no lo escribe en el log", async () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("PREVIEW_LOGIN_EMAIL", email);
    const malo = "texto-plano-no-es-hash";
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", malo);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(await autenticarPreview(email, password)).toBeNull();
    const texto = warn.mock.calls.flat().join(" ");
    expect(texto).toMatch(/formato scrypt/);
    expect(texto).not.toContain(malo);
    expect(texto).not.toContain(password);
    expect(texto).not.toContain(email);
  });
});

describe("datosMinimosPreview", () => {
  it("no trae identificadores de Stripe", () => {
    const datos = datosMinimosPreview("dueno@example.com");
    expect(datos.usuario.email).toBe("dueno@example.com");
    expect(datos.creditos.saldo_actual).toBe(0);
    expect(datos.transacciones_recientes).toEqual([]);
    expect(datos.suscripcion.stripe_customer_id).toBe("");
    expect(datos.suscripcion.stripe_subscription_id).toBe("");
    expect(datos.resumen.puede_cancelar).toBe(false);
    expect(JSON.stringify(datos)).not.toMatch(/cus_|sub_/);
  });
});
