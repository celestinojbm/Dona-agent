import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const RAIZ = path.resolve(__dirname, "..");

function archivos(dir: string): string[] {
  const salida: string[] = [];
  for (const nombre of readdirSync(dir)) {
    const full = path.join(dir, nombre);
    if (statSync(full).isDirectory()) salida.push(...archivos(full));
    else salida.push(full);
  }
  return salida;
}

describe("paleta de la landing v2", () => {
  const fuentes = [
    ...archivos(path.join(RAIZ, "components/v2")),
    path.join(RAIZ, "app/v2.css"),
    path.join(RAIZ, "app/page.tsx"),
  ].filter((archivo) => /\.(tsx|ts|css)$/.test(archivo) && !archivo.endsWith(".test.ts"));

  it("no usa sombras, gradientes de color ni el fucsia fuera del logo", () => {
    for (const archivo of fuentes) {
      const texto = readFileSync(archivo, "utf8");
      const relativo = path.relative(RAIZ, archivo);
      expect(texto, relativo).not.toMatch(/box-shadow/i);
      expect(texto, relativo).not.toMatch(/#5b5bf0|#f97316|#8f8ff7/i);
      if (!relativo.endsWith("components/v2/logo.tsx")) {
        expect(texto, relativo).not.toMatch(/#e64263/i);
      }
    }
    const logo = readFileSync(path.join(RAIZ, "components/v2/logo.tsx"), "utf8");
    expect(logo).toMatch(/#E64263/);
  });
});
