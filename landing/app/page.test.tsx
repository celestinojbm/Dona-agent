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
    // El numero se renderiza como `target` por defecto (SSR / sin JS / reduced-motion):
    // sin flash de 0. El count-up es enhancement client-side via data-countup.
    expect(pageSource).toContain("data-countup={target}>{target}</span>");
  });

  it("la apertura cinematografica nunca tapa ni bloquea el contenido si la animacion no corre", () => {
    // Fail-safe (LTX iter 31): el telon de "fade from black" arranca invisible y
    // sin capturar el puntero. Si la animacion CSS no se ejecuta queda en opacity 0
    // → jamas cubre la pagina. Mismo espiritu que el reveal de [data-fade].
    const introBlock = globalCss.match(/\.cinematic-intro\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? "";
    expect(introBlock).toMatch(/opacity:\s*0/);
    expect(introBlock).toMatch(/pointer-events:\s*none/);
    // Respeta prefers-reduced-motion: sin fundido (animation: none), telon invisible.
    expect(globalCss).toMatch(/\.cinematic-intro\s*\{[^}]*animation:\s*none/);
  });
});
