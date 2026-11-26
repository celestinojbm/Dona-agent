/** @vitest-environment jsdom */
// landing/app/interno/control-room/page.test.tsx — Gate de servidor del
// Control Room. Sin la allowlist (o en pausa) la ruta responde 404 sin
// renderizar nada del panel.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";

const estado = vi.hoisted(() => ({ pausa: true, cookie: undefined as string | undefined }));
const TOKEN = "token-del-dueno-de-prueba";

const { authSpy, notFoundSpy } = vi.hoisted(() => ({
  authSpy: vi.fn(),
  notFoundSpy: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/auth", () => ({ auth: authSpy }));
vi.mock("next/navigation", () => ({ notFound: notFoundSpy }));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (nombre: string) =>
      nombre === "panel_ing_token" && estado.cookie !== undefined
        ? { name: nombre, value: estado.cookie }
        : undefined,
  }),
}));
vi.mock("@/lib/pausa", () => ({
  get DONA_EN_PAUSA() {
    return estado.pausa;
  },
}));

import ControlRoomPage from "./page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllEnvs();
});

describe("Control Room · gate de servidor", () => {
  beforeEach(() => {
    estado.pausa = false;
    estado.cookie = undefined;
    vi.stubEnv("PANEL_INGENIERIA_TOKEN", TOKEN);
  });

  it("responde 404 durante la pausa sin leer la sesión", async () => {
    estado.pausa = true;
    await expect(ControlRoomPage()).rejects.toThrow("NEXT_NOT_FOUND");
    expect(authSpy).not.toHaveBeenCalled();
  });

  it("responde 404 sin sesión", async () => {
    authSpy.mockResolvedValue(null);
    await expect(ControlRoomPage()).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("responde 404 a un cliente con sesión válida fuera de la allowlist", async () => {
    authSpy.mockResolvedValue({ user: { email: "cliente@example.com" } });
    await expect(ControlRoomPage()).rejects.toThrow("NEXT_NOT_FOUND");
  });

  // Sesión con el correo del dueño pero sin su token: es lo que obtiene
  // quien paga en Stripe con ese correo (no verificado) y su propio teléfono.
  it("responde 404 al correo del dueño sin la cookie del token", async () => {
    authSpy.mockResolvedValue({ user: { email: "celestinojbm@gmail.com" } });
    await expect(ControlRoomPage()).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("responde 404 al correo del dueño con un token incorrecto", async () => {
    authSpy.mockResolvedValue({ user: { email: "celestinojbm@gmail.com" } });
    estado.cookie = "token-falso";
    await expect(ControlRoomPage()).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("responde 404 si PANEL_INGENIERIA_TOKEN no está configurado", async () => {
    vi.stubEnv("PANEL_INGENIERIA_TOKEN", "");
    authSpy.mockResolvedValue({ user: { email: "celestinojbm@gmail.com" } });
    estado.cookie = "";
    await expect(ControlRoomPage()).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("renderiza el panel para la allowlist interna con el token del dueño", async () => {
    authSpy.mockResolvedValue({ user: { email: "celestinojbm@gmail.com" } });
    estado.cookie = TOKEN;
    render(await ControlRoomPage());
    expect(screen.getByText(/Dona Control Room/i)).toBeInTheDocument();
    expect(notFoundSpy).not.toHaveBeenCalled();
  });
});
