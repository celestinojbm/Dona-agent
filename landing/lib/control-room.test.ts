import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { correoEnAllowlist, puedeVerControlRoomInterno } from "./control-room";

const TOKEN = "token-del-dueno-de-prueba";

describe("correoEnAllowlist", () => {
  it("permite el email interno de Celestino", () => {
    expect(correoEnAllowlist("celestinojbm@gmail.com")).toBe(true);
  });

  it("normaliza espacios y mayúsculas", () => {
    expect(correoEnAllowlist("  CELESTINOJBM@GMAIL.COM ")).toBe(true);
  });

  it("bloquea usuarios sin allowlist", () => {
    expect(correoEnAllowlist("cliente@example.com")).toBe(false);
    expect(correoEnAllowlist(null)).toBe(false);
  });
});

describe("puedeVerControlRoomInterno", () => {
  beforeEach(() => {
    vi.stubEnv("PANEL_INGENIERIA_TOKEN", TOKEN);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("permite correo en allowlist con el token del dueño", () => {
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com", TOKEN)).toBe(true);
  });

  // El correo de la sesión sale del customer de Stripe y no está verificado:
  // quien pague con el correo del dueño obtiene una sesión con ese correo.
  it("bloquea el correo del dueño sin token", () => {
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com", undefined)).toBe(false);
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com", "")).toBe(false);
  });

  it("bloquea el correo del dueño con un token incorrecto", () => {
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com", "otro")).toBe(false);
  });

  it("bloquea el token correcto con un correo fuera de la allowlist", () => {
    expect(puedeVerControlRoomInterno("cliente@example.com", TOKEN)).toBe(false);
    expect(puedeVerControlRoomInterno(null, TOKEN)).toBe(false);
  });

  it("fail-closed: sin PANEL_INGENIERIA_TOKEN configurado nadie entra", () => {
    vi.stubEnv("PANEL_INGENIERIA_TOKEN", "");
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com", "")).toBe(false);
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com", TOKEN)).toBe(false);
  });
});

// Frontera cliente/servidor: ningún módulo "use client" puede importar la
// allowlist, los datos del Control Room ni su panel. Si alguien lo hace,
// el correo interno y el índice de agent-runs volverían al bundle público.
describe("Control Room · fuera del bundle cliente", () => {
  it("ningún archivo 'use client' importa módulos del Control Room", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const { join } = await import("node:path");
    const raiz = process.cwd();
    const archivos: string[] = [];
    const recorrer = (dir: string) => {
      for (const nombre of readdirSync(dir)) {
        if (nombre === "node_modules" || nombre.startsWith(".")) continue;
        const ruta = join(dir, nombre);
        if (statSync(ruta).isDirectory()) recorrer(ruta);
        else if (/\.(ts|tsx)$/.test(nombre) && !/\.test\./.test(nombre)) archivos.push(ruta);
      }
    };
    ["app", "components", "lib"].forEach((d) => recorrer(join(raiz, d)));
    const infractores = archivos.filter((ruta) => {
      const src = readFileSync(ruta, "utf-8");
      const esCliente = /^\s*["']use client["']/m.test(src.slice(0, 400));
      return (
        esCliente &&
        /from\s+["'][^"']*(control-room|panel-control-room)[^"']*["']/.test(src)
      );
    });
    expect(infractores).toEqual([]);
  });

  it("la allowlist y los datos son solo servidor", async () => {
    const { readFileSync } = await import("node:fs");
    for (const archivo of ["lib/control-room.ts", "lib/control-room-data.ts"]) {
      expect(readFileSync(archivo, "utf-8")).toMatch(/^import "server-only";/m);
    }
  });
});
