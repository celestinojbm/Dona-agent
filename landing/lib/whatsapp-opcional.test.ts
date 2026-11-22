// landing/lib/whatsapp-opcional.test.ts — WhatsApp apagado como integración
// opcional: la bandera es una constante en código y el envío por Whapi no
// sale aunque exista WHAPI_TOKEN.

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  WHATSAPP_HABILITADO,
  siguientePasoSinWhatsApp,
  urlWhatsApp,
} from "./whatsapp-opcional";
import { STEPS } from "@/app/dashboard/tour";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("WhatsApp como integración opcional", () => {
  it("está apagado en código", () => {
    expect(WHATSAPP_HABILITADO).toBe(false);
  });

  it("sustituye los textos del backend que mandan a WhatsApp", () => {
    expect(
      siguientePasoSinWhatsApp("Escribe 'continuar diagnóstico' a Dona por WhatsApp."),
    ).toMatch(/Cuéntale a Dona en el chat/);
    expect(siguientePasoSinWhatsApp("Completa tu perfil.")).toBe("Completa tu perfil.");
  });

  it("conserva el enlace wa.me para cuando se reactive", () => {
    expect(urlWhatsApp("hola")).toBe("https://wa.me/?text=hola");
  });

  it("no llama a Whapi aunque exista WHAPI_TOKEN", async () => {
    vi.stubEnv("WHAPI_TOKEN", "token-de-prueba");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const { sendWhatsAppMessage } = await import("./whatsapp");
    expect(await sendWhatsAppMessage("15550000000", "hola")).toBe(false);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("el tour no menciona WhatsApp en ningún paso", () => {
    for (const paso of STEPS) {
      expect(`${paso.titulo} ${paso.descripcion}`).not.toMatch(/whats\s*app/i);
    }
  });
});
