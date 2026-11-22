/**
 * @vitest-environment jsdom
 */
// Formulario de la lista de espera: alta, canje de invitación y errores.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import ListaEsperaForm from "./lista-espera-form";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function responde(status: number, cuerpo: unknown) {
  const spy = vi.fn().mockResolvedValue(new Response(JSON.stringify(cuerpo), { status }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("ListaEsperaForm", () => {
  it("deja el correo y confirma que está en la lista", async () => {
    const spy = responde(200, { ok: true, estado: "en_espera" });
    render(<ListaEsperaForm />);
    fireEvent.change(screen.getByLabelText("Correo"), { target: { value: "ana@negocio.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Unirme a la lista" }));
    await waitFor(() => expect(screen.getByText("Ya estás en la lista")).toBeInTheDocument());
    const [ruta, init] = spy.mock.calls[0];
    expect(ruta).toBe("/api/lista-espera");
    expect(JSON.parse(init.body)).toEqual({ email: "ana@negocio.com", empresa: "" });
  });

  it("canjea un código de invitación", async () => {
    const spy = responde(200, { ok: true, estado: "invitado" });
    render(<ListaEsperaForm />);
    fireEvent.click(screen.getByRole("button", { name: "Tengo un código de invitación" }));
    fireEvent.change(screen.getByLabelText("Correo"), { target: { value: "ana@negocio.com" } });
    fireEvent.change(screen.getByLabelText("Código de invitación"), {
      target: { value: "DONA-PILOTO-2026" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Usar invitación" }));
    await waitFor(() => expect(screen.getByText("Invitación aceptada")).toBeInTheDocument());
    expect(spy.mock.calls[0][0]).toBe("/api/lista-espera/invitacion");
  });

  it("muestra un error claro si el código no es válido", async () => {
    responde(403, { ok: false, error: "codigo_invalido" });
    render(<ListaEsperaForm />);
    fireEvent.click(screen.getByRole("button", { name: "Tengo un código de invitación" }));
    fireEvent.change(screen.getByLabelText("Correo"), { target: { value: "a@negocio.com" } });
    fireEvent.change(screen.getByLabelText("Código de invitación"), { target: { value: "OTRO-CODIGO" } });
    fireEvent.click(screen.getByRole("button", { name: "Usar invitación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no es válido/);
  });

  it("si la red falla, pide reintentar sin perder lo escrito", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<ListaEsperaForm />);
    fireEvent.change(screen.getByLabelText("Correo"), { target: { value: "ana@negocio.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Unirme a la lista" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Inténtalo de nuevo/);
    expect(screen.getByLabelText("Correo")).toHaveValue("ana@negocio.com");
  });
});
