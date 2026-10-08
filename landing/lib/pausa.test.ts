// landing/lib/pausa.test.ts — El interruptor de pausa vive en código.

import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("lib/pausa · interruptor central", () => {
  it("Dona está en pausa", async () => {
    const { DONA_EN_PAUSA } = await import("./pausa");
    expect(DONA_EN_PAUSA).toBe(true);
  });

  it("no depende de variables de entorno (una env no puede despausar)", async () => {
    vi.resetModules();
    vi.stubEnv("DONA_EN_PAUSA", "false");
    vi.stubEnv("NEXT_PUBLIC_DONA_EN_PAUSA", "false");
    const { DONA_EN_PAUSA } = await import("./pausa");
    expect(DONA_EN_PAUSA).toBe(true);
    vi.unstubAllEnvs();

    const fuente = readFileSync(join(process.cwd(), "lib/pausa.ts"), "utf-8");
    expect(fuente).not.toContain("process.env");
  });

  it("el aviso es el texto acordado", async () => {
    const { MENSAJE_PAUSA, CUERPO_PAUSA } = await import("./pausa");
    expect(MENSAJE_PAUSA).toBe(
      "Dona está en pausa. No aceptamos nuevas suscripciones ni compras.",
    );
    expect(CUERPO_PAUSA).toEqual({ error: "dona_en_pausa", mensaje: MENSAJE_PAUSA });
  });
});
