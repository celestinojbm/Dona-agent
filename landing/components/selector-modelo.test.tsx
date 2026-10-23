/**
 * @vitest-environment jsdom
 */
// Tests del selector de modelo (F23): radiogroup accesible, opción Auto, modelo
// recomendado marcado con texto, y callback de selección.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { SelectorModelo } from "./selector-modelo";

afterEach(cleanup);

const MODELOS = [
  { id: "claude-sonnet-4-5", nombre: "Claude Sonnet 4.5", proveedor: "anthropic" },
  { id: "gpt-4o", nombre: "GPT-4o", proveedor: "openai" },
];

describe("SelectorModelo", () => {
  it("expone un radiogroup con Auto + modelos", () => {
    render(<SelectorModelo modelos={MODELOS} seleccionado="auto" onSeleccionar={() => {}} />);
    expect(screen.getByRole("radiogroup", { name: "Modelo" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Auto/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Claude Sonnet/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /GPT-4o/ })).toBeInTheDocument();
  });

  it("marca el seleccionado con aria-checked", () => {
    render(<SelectorModelo modelos={MODELOS} seleccionado="gpt-4o" onSeleccionar={() => {}} />);
    expect(screen.getByRole("radio", { name: /GPT-4o/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: /Auto/ })).toHaveAttribute("aria-checked", "false");
  });

  it("muestra 'recomendado' como texto en el modelo recomendado", () => {
    render(
      <SelectorModelo
        modelos={MODELOS}
        seleccionado="auto"
        onSeleccionar={() => {}}
        recomendado="gpt-4o"
      />,
    );
    expect(screen.getByText("recomendado")).toBeInTheDocument();
  });

  it("llama onSeleccionar al elegir", () => {
    const onSel = vi.fn();
    render(<SelectorModelo modelos={MODELOS} seleccionado="auto" onSeleccionar={onSel} />);
    fireEvent.click(screen.getByRole("radio", { name: /Claude Sonnet/ }));
    expect(onSel).toHaveBeenCalledWith("claude-sonnet-4-5");
  });
});
