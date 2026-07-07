import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = process.cwd();
const pageSource = readFileSync(join(repoRoot, "app/page.tsx"), "utf-8");
const globalCss = readFileSync(join(repoRoot, "app/globals.css"), "utf-8");

describe("landing pública · narrativa canónica", () => {
  it("presenta a Dona como plataforma-agente de negocio (no 'chatbot de WhatsApp')", () => {
    // Narrativa canónica: plataforma-agente de negocio y ejecución controlada.
    expect(pageSource).toContain("Plataforma-agente de negocio");
    // WhatsApp aparece solo como canal de entrada.
    expect(pageSource).toContain("WhatsApp");
    // La FAQ desmiente explícitamente la reducción a chatbot de WhatsApp.
    expect(pageSource).toContain("¿Dona es un chatbot de WhatsApp?");
    // Guardia anti-regresión: no vender Dona como asistente/chatbot de WhatsApp.
    expect(pageSource).not.toContain("asistente en WhatsApp");
    expect(pageSource).not.toContain("agente de WhatsApp");
  });

  it("cubre las secciones clave del brief", () => {
    const claves = [
      "De intención a ejecución", // loop
      "Plataforma", // módulos
      "Control Room",
      "Lo que Dona produce", // galería de outputs
      "Dona no ejecuta a ciegas", // control humano (obligatoria)
      "Audit trail",
      "Preguntas frecuentes", // FAQ
    ];
    for (const k of claves) expect(pageSource).toContain(k);
  });

  it("muestra el loop de 6 pasos (entrada → medición)", () => {
    for (const paso of [
      "Entrada",
      "Contexto",
      "Producción",
      "Permisos",
      "Ejecución",
      "Medición",
    ]) {
      expect(pageSource).toContain(paso);
    }
  });

  it("conserva el checkout Stripe con los planes Premium y Pro", () => {
    // El flujo de checkout server-side no debe romperse: POST /api/checkout { plan }.
    expect(pageSource).toContain("/api/checkout");
    expect(pageSource).toContain("handleCheckout");
    // Los planes de suscripción se envían con las claves que espera el backend.
    expect(pageSource).toContain('plan: "premium"');
    expect(pageSource).toContain('plan: "pro"');
    expect(pageSource).toContain("$20");
    expect(pageSource).toContain("$40");
  });

  it("elimina testimonios inventados y pain-stats sin sustanciar (riesgo FTC)", () => {
    // Ningún testimonio inventado de la landing vieja.
    expect(pageSource).not.toContain("Carlos Montoya");
    expect(pageSource).not.toContain("Valeria Restrepo");
    // Ninguna estadística de dolor sin fuente.
    expect(pageSource).not.toContain("painStats");
    expect(pageSource).not.toContain("14h");
    // Sin promesas de ingresos garantizados ni "Fundadores".
    expect(pageSource).not.toContain("Fundadores");
    expect(pageSource).not.toMatch(/ingresos garantizados/i);
  });

  it("no deja contenido crítico invisible si falla el reveal on-scroll", () => {
    // El reveal solo oculta contenido cuando JS marca [data-reveal-root="ready"];
    // sin JS (SSR) el contenido es visible. Guardia: el estado base de
    // [data-reveal] NO debe poner opacity:0 sin el gate "ready".
    const gatedBlock =
      globalCss.match(
        /\[data-reveal-root="ready"\]\s*\[data-reveal\]\s*\{(?<body>[^}]*)\}/,
      )?.groups?.body ?? "";
    expect(gatedBlock).toMatch(/opacity\s*:\s*0/);
    // Y no debe existir una regla global [data-reveal] { opacity: 0 } sin gate.
    expect(globalCss).not.toMatch(/^\s*\[data-reveal\]\s*\{[^}]*opacity\s*:\s*0/m);
  });

  it("usa la base clara premium (fondo blanco, un solo acento de marca)", () => {
    expect(globalCss).toContain("--bg: #ffffff");
    expect(globalCss).toContain("--brand: #5b5bf0");
    // El chrome oscuro viejo salió del layout: sin video de fondo, overlay
    // negro, noise-overlay ni ambient blobs.
    const layout = readFileSync(join(repoRoot, "app/layout.tsx"), "utf-8");
    expect(layout).not.toContain("hero.mp4");
    expect(layout).not.toContain("noise-overlay");
    expect(layout).not.toContain("ambient-blob");
    expect(layout).not.toContain("bg-black");
    // El pixel de Facebook se conserva.
    expect(layout).toContain("connect.facebook.net");
  });
});
