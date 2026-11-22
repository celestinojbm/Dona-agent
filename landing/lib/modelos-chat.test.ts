// landing/lib/modelos-chat.test.ts — El selector solo ofrece lo que funciona.

import { describe, expect, it } from "vitest";
import {
  CATALOGO_CHAT,
  HAY_SELECCION_DE_MODELO,
  MODELO_AUTO,
  MODELOS_CHAT,
  nombreModelo,
} from "./modelos-chat";

describe("modelos del chat", () => {
  it("Automático es el modo por defecto", () => {
    expect(MODELO_AUTO).toBe("auto");
    expect(nombreModelo(MODELO_AUTO)).toBe("Automático");
  });

  it("solo expone modelos que el backend aplica en el chat", () => {
    const esperados = CATALOGO_CHAT.filter((m) => m.aplicaEnChat).map((m) => m.id);
    expect(MODELOS_CHAT.map((m) => m.id)).toEqual(esperados);
  });

  it("hoy /internal/chat no aplica ninguno: sin selector", () => {
    expect(MODELOS_CHAT).toEqual([]);
    expect(HAY_SELECCION_DE_MODELO).toBe(false);
  });

  it("un id desconocido u oculto se muestra como Automático", () => {
    expect(nombreModelo("gpt-4o")).toBe("Automático");
  });
});
