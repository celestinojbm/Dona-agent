import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const pageSource = readFileSync(join(repoRoot, "app/page.tsx"), "utf-8");
const globalCss = readFileSync(join(repoRoot, "app/globals.css"), "utf-8");
const motionSource = readFileSync(join(repoRoot, "app/useCinematicMotion.ts"), "utf-8");

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

  it("el tilt 3D de las cards es solo transform y respeta reduced-motion", () => {
    // iter 8: las cards se inclinan hacia el cursor (enhancement client-side).
    expect(pageSource).toContain("data-tilt");
    // El tilt anima rotationX/Y (transform), no opacity → la card jamas queda
    // invisible si el efecto no corre.
    expect(motionSource).toContain("[data-tilt]");
    expect(motionSource).toContain("rotationX");
    expect(motionSource).not.toContain("opacity: 0");
    // El motor de movimiento se salta TODO si el usuario pidio menos movimiento.
    expect(motionSource).toContain('matchMedia("(prefers-reduced-motion: reduce)").matches');
    // El CSS no deja la card oculta: data-tilt solo da hint de compositing.
    const tiltBlock = globalCss.match(/\.glass-card\[data-tilt\]\s*\{(?<body>[^}]*)\}/)?.groups?.body ?? "";
    expect(tiltBlock).not.toMatch(/opacity\s*:\s*0\s*;/);
  });
});
