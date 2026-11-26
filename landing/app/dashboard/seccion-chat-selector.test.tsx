/**
 * @vitest-environment jsdom
 */
// Cuando un modelo SÍ se aplica en el backend (aplicaEnChat: true), el chat
// monta el selector con "Automático" + ese modelo, y nada más.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

vi.mock("@/lib/modelos-chat", () => ({
  MODELO_AUTO: "auto",
  HAY_SELECCION_DE_MODELO: true,
  MODELOS_CHAT: [{ id: "modelo-real", nombre: "Modelo real", proveedor: "Anthropic" }],
  nombreModelo: (id: string) => (id === "auto" ? "Automático" : "Modelo real"),
}));

import SeccionChat from "./seccion-chat";

afterEach(cleanup);

describe("SeccionChat · selector con un modelo real", () => {
  it("abre el selector con Automático y el modelo que funciona", () => {
    Element.prototype.scrollIntoView = vi.fn();
    render(<SeccionChat />);
    fireEvent.click(screen.getByRole("button", { name: "Modelo: Automático" }));
    expect(screen.getByRole("radio", { name: /Automático/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    fireEvent.click(screen.getByRole("radio", { name: /Modelo real/ }));
    expect(screen.getByRole("button", { name: "Modelo: Modelo real" })).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });
});
