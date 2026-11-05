/** @vitest-environment jsdom */
// landing/app/lista-espera.test.tsx — Formulario de lista de espera en el inicio.

import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/auth", () => ({ auth: vi.fn() }));

import Home from "./page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("lista de espera en /", () => {
  it("muestra correo, teléfono opcional, botón, ayuda y enlace a privacidad", () => {
    render(Home());
    expect(screen.getByRole("heading", { name: "Dona está completo" })).toBeInTheDocument();
    const email = screen.getByLabelText("Tu correo");
    expect(email).toHaveAttribute("type", "email");
    expect(email).toBeRequired();
    const tel = screen.getByLabelText("Tu teléfono (opcional)");
    expect(tel).toHaveAttribute("type", "tel");
    expect(tel).not.toBeRequired();
    expect(screen.getByRole("button", { name: "Avísame" })).toBeInTheDocument();
    expect(
      screen.getByText(/Te escribiremos solo para avisarte cuando haya plazas\./),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacidad" })).toHaveAttribute(
      "href",
      "/politica-de-privacidad",
    );
  });

  it("envía a /api/waitlist y muestra el éxito", async () => {
    const fetchSpy = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);
    render(Home());
    fireEvent.change(screen.getByLabelText("Tu correo"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("Tu teléfono (opcional)"), {
      target: { value: "+58 412 000 0000" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Avísame" }));
    await waitFor(() =>
      expect(screen.getByText("Listo. Te avisaremos cuando haya plazas.")).toBeInTheDocument(),
    );
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/waitlist");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "a@b.co",
      phone: "+58 412 000 0000",
      empresa: "",
    });
  });

  it("muestra el error si el servidor rechaza", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 502 })));
    render(Home());
    fireEvent.change(screen.getByLabelText("Tu correo"), { target: { value: "a@b.co" } });
    fireEvent.click(screen.getByRole("button", { name: "Avísame" }));
    await waitFor(() =>
      expect(
        screen.getByText("No pudimos registrar tu correo. Inténtalo de nuevo."),
      ).toBeInTheDocument(),
    );
  });
});
