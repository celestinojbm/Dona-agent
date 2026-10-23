/**
 * @vitest-environment jsdom
 */
// Tests de la comparación lado a lado (F23): estado vacío, columnas por modelo,
// carga, error por columna, chips de sugerencias y callbacks.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ComparacionModelos } from "./comparacion-modelos";

afterEach(cleanup);

describe("ComparacionModelos", () => {
  it("estado vacío sin respuestas", () => {
    render(<ComparacionModelos respuestas={[]} />);
    expect(screen.getByText(/Elige dos modelos para comparar/)).toBeInTheDocument();
  });

  it("muestra una columna por modelo con su respuesta", () => {
    render(
      <ComparacionModelos
        respuestas={[
          { modelo: "gpt-4o", texto: "respuesta A" },
          { modelo: "claude-sonnet-4-5", texto: "respuesta B" },
        ]}
      />,
    );
    expect(screen.getByRole("region", { name: /Respuesta de gpt-4o/ })).toBeInTheDocument();
    expect(screen.getByText("respuesta A")).toBeInTheDocument();
    expect(screen.getByText("respuesta B")).toBeInTheDocument();
  });

  it("estado de carga por columna", () => {
    render(<ComparacionModelos respuestas={[{ modelo: "gpt-4o", cargando: true }]} />);
    const region = screen.getByRole("region", { name: /gpt-4o/ });
    expect(within(region).getByLabelText("Cargando")).toBeInTheDocument();
  });

  it("estado de error por columna con role alert", () => {
    render(<ComparacionModelos respuestas={[{ modelo: "gpt-4o", error: "falló el proveedor" }]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("falló el proveedor");
  });

  it("elige la respuesta ganadora", () => {
    const onElegir = vi.fn();
    render(
      <ComparacionModelos
        respuestas={[{ modelo: "gpt-4o", texto: "A" }]}
        onElegir={onElegir}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Usar esta" }));
    expect(onElegir).toHaveBeenCalledWith("gpt-4o");
  });

  it("renderiza chips de sugerencias y dispara onChip", () => {
    const onChip = vi.fn();
    render(
      <ComparacionModelos
        respuestas={[{ modelo: "gpt-4o", texto: "A" }]}
        sugerencias={{ respuestas: ["Confirmar"], acciones: ["Enviar borrador"] }}
        onChip={onChip}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Enviar borrador" }));
    expect(onChip).toHaveBeenCalledWith("Enviar borrador");
  });
});
