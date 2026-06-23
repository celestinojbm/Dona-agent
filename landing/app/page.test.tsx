import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const pageSource = readFileSync(join(repoRoot, "app/page.tsx"), "utf-8");
const globalCss = readFileSync(join(repoRoot, "app/globals.css"), "utf-8");

describe("landing publica · legibilidad y reveal", () => {
  it("no deja contenido clave invisible si falla el reveal on-scroll", () => {
    const pendingFadeBlock = globalCss.match(/\[data-fade="pending"\]\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? "";

    expect(pendingFadeBlock).not.toMatch(/opacity\s*:\s*0\s*;/);
  });

  it("presenta a Dona como plataforma-agente de ejecucion (no 'agente de WhatsApp'), con WhatsApp como canal", () => {
    // Narrativa canonica: plataforma-agente de negocio y ejecucion controlada.
    expect(pageSource).toContain("plataforma-agente");
    // WhatsApp es canal de entrada (CTA), no la identidad del producto.
    expect(pageSource).toContain("Empezar en WhatsApp");
    // Guardia anti-regresion: no volver a reducir Dona a "agente de WhatsApp".
    expect(pageSource).not.toContain("Tu agente operativo");
    expect(pageSource).not.toContain("Your operating agent");
  });

  it("muestra metricas reales aunque la animacion del contador no se ejecute", () => {
    expect(pageSource).toContain("const [count] = useState(target)");
    expect(pageSource).not.toContain("const [count, setCount] = useState(0)");
  });
});
