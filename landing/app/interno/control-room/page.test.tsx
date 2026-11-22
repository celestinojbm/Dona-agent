/** @vitest-environment jsdom */
// landing/app/interno/control-room/page.test.tsx — Gate de servidor del
// Control Room. Sin la allowlist (o en pausa) la ruta responde 404 sin
// renderizar nada del panel.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";

const estado = vi.hoisted(() => ({ pausa: true }));

const { authSpy, notFoundSpy } = vi.hoisted(() => ({
  authSpy: vi.fn(),
  notFoundSpy: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/auth", () => ({ auth: authSpy }));
vi.mock("next/navigation", () => ({ notFound: notFoundSpy }));
vi.mock("@/lib/pausa", () => ({
  get DONA_EN_PAUSA() {
    return estado.pausa;
  },
}));

import ControlRoomPage from "./page";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Control Room · gate de servidor", () => {
  beforeEach(() => {
    estado.pausa = false;
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

  it("renderiza el panel para la allowlist interna", async () => {
    authSpy.mockResolvedValue({ user: { email: "celestinojbm@gmail.com" } });
    render(await ControlRoomPage());
    expect(screen.getByText(/Dona Control Room/i)).toBeInTheDocument();
    expect(notFoundSpy).not.toHaveBeenCalled();
  });
});
