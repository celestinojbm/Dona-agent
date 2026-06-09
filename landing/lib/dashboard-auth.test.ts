// landing/lib/dashboard-auth.test.ts
// Tests del gate de formato del password (rank 4). El gate rechaza passwords
// que no matchean el formato derivado ANTES de pegarle a Stripe / contar lockout.

import { describe, it, expect } from "vitest";
import { tienePasswordFormatoValido } from "./dashboard-auth";

describe("tienePasswordFormatoValido", () => {
  it("acepta el formato derivado: dona- + 12 hex", () => {
    expect(tienePasswordFormatoValido("dona-0123456789ab")).toBe(true);
    expect(tienePasswordFormatoValido("dona-ffffffffffff")).toBe(true);
    expect(tienePasswordFormatoValido("dona-000000000000")).toBe(true);
  });

  it("rechaza longitud incorrecta del sufijo", () => {
    expect(tienePasswordFormatoValido("dona-0123456789a")).toBe(false); // 11
    expect(tienePasswordFormatoValido("dona-0123456789abc")).toBe(false); // 13
  });

  it("rechaza no-hex y mayúsculas", () => {
    expect(tienePasswordFormatoValido("dona-0123456789AB")).toBe(false);
    expect(tienePasswordFormatoValido("dona-0123456789zz")).toBe(false);
    expect(tienePasswordFormatoValido("dona-0123456789g0")).toBe(false);
  });

  it("rechaza prefijo faltante o distinto", () => {
    expect(tienePasswordFormatoValido("0123456789ab")).toBe(false);
    expect(tienePasswordFormatoValido("dona0123456789ab")).toBe(false);
    expect(tienePasswordFormatoValido("DONA-0123456789ab")).toBe(false);
  });

  it("rechaza vacío, no-strings y null/undefined", () => {
    expect(tienePasswordFormatoValido("")).toBe(false);
    expect(tienePasswordFormatoValido(undefined)).toBe(false);
    expect(tienePasswordFormatoValido(null)).toBe(false);
    expect(tienePasswordFormatoValido(12345)).toBe(false);
  });

  it("rechaza intentos con saltos de línea (no multilinea)", () => {
    expect(tienePasswordFormatoValido("dona-0123456789ab\nextra")).toBe(false);
    expect(tienePasswordFormatoValido("dona-0123456789ab\n")).toBe(false);
  });
});
