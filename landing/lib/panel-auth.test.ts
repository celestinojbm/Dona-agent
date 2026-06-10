// landing/lib/panel-auth.test.ts
// Tests del gate del panel de ingeniería. Foco: FAIL-CLOSED (sin env var
// configurado nadie entra) y validación correcta del token.

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { esTokenPanelValido } from "./panel-auth";

const ENV_ORIGINAL = { ...process.env };

beforeEach(() => {
  process.env.PANEL_INGENIERIA_TOKEN = "token-secreto-del-dueno";
});

afterEach(() => {
  process.env = { ...ENV_ORIGINAL };
});

describe("esTokenPanelValido — fail-closed", () => {
  it("rechaza TODO si PANEL_INGENIERIA_TOKEN no está configurado", () => {
    delete process.env.PANEL_INGENIERIA_TOKEN;
    expect(esTokenPanelValido("token-secreto-del-dueno")).toBe(false);
    expect(esTokenPanelValido("")).toBe(false);
  });

  it("rechaza si el env var está vacío o solo whitespace", () => {
    process.env.PANEL_INGENIERIA_TOKEN = "   ";
    expect(esTokenPanelValido("   ")).toBe(false);
  });

  it("rechaza candidato vacío, null o undefined", () => {
    expect(esTokenPanelValido("")).toBe(false);
    expect(esTokenPanelValido(null)).toBe(false);
    expect(esTokenPanelValido(undefined)).toBe(false);
  });
});

describe("esTokenPanelValido — validación", () => {
  it("acepta el token correcto", () => {
    expect(esTokenPanelValido("token-secreto-del-dueno")).toBe(true);
  });

  it("rechaza un token incorrecto", () => {
    expect(esTokenPanelValido("token-equivocado")).toBe(false);
  });

  it("rechaza prefijos y sufijos del token correcto", () => {
    expect(esTokenPanelValido("token-secreto-del-duen")).toBe(false);
    expect(esTokenPanelValido("token-secreto-del-duenoX")).toBe(false);
  });

  it("el env var se compara con trim (copy-paste con espacios)", () => {
    process.env.PANEL_INGENIERIA_TOKEN = "  abc123  ";
    expect(esTokenPanelValido("abc123")).toBe(true);
  });
});
