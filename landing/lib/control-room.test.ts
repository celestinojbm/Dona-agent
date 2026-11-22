import { describe, expect, it } from "vitest";
import { puedeVerControlRoomInterno } from "./control-room";

describe("puedeVerControlRoomInterno", () => {
  it("permite el email interno de Celestino", () => {
    expect(puedeVerControlRoomInterno("celestinojbm@gmail.com")).toBe(true);
  });

  it("normaliza espacios y mayúsculas", () => {
    expect(puedeVerControlRoomInterno("  CELESTINOJBM@GMAIL.COM ")).toBe(true);
  });

  it("bloquea usuarios sin allowlist", () => {
    expect(puedeVerControlRoomInterno("cliente@example.com")).toBe(false);
    expect(puedeVerControlRoomInterno(null)).toBe(false);
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
