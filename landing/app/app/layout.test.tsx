// landing/app/app/layout.test.tsx — /app es 404 si el piloto está apagado.

import { afterEach, describe, expect, it, vi } from "vitest";

const notFound = vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND");
});
const sesionApp = vi.fn();
vi.mock("next/navigation", () => ({ notFound, redirect: vi.fn() }));
vi.mock("@/lib/app-sesion", () => ({ sesionApp }));
vi.mock("./acciones", () => ({ salir: vi.fn() }));

const { default: LayoutApp, metadata } = await import("./layout");

afterEach(() => vi.unstubAllEnvs());

describe("layout /app", () => {
  it("piloto apagado → notFound sin leer la sesión", async () => {
    vi.stubEnv("DONA_APP_PILOTO_ENABLED", "");
    await expect(LayoutApp({ children: null })).rejects.toThrow("NEXT_NOT_FOUND");
    expect(sesionApp).not.toHaveBeenCalled();
  });

  it("piloto encendido → renderiza y no se indexa", async () => {
    vi.stubEnv("DONA_APP_PILOTO_ENABLED", "true");
    sesionApp.mockResolvedValue(null);
    await expect(LayoutApp({ children: null })).resolves.toBeTruthy();
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
