/**
 * @vitest-environment jsdom
 */
// Tests del panel del plan vivo (F14). Verifican estructura accesible y estados
// desde datos (sin red): región aria-live, estado textual (no sólo color),
// numeración, motivo de fallo, y el pulso con motion-reduce desactivable.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { PlanVivoPanel, type PlanVivo } from "./plan-vivo-panel";

afterEach(cleanup);

const PLAN: PlanVivo = {
  estado: "en_curso",
  coste_maximo: 5,
  pasos: [
    { id: "p1", titulo: "Buscar", estado: "completado" },
    { id: "p2", titulo: "Redactar", estado: "en_curso" },
    { id: "p3", titulo: "Enviar", estado: "fallido", resultado: "sin destinatario" },
    { id: "p4", titulo: "Cerrar", estado: "pendiente" },
  ],
};

describe("PlanVivoPanel", () => {
  it("muestra 'Dona trabajando…' en curso y los pasos", () => {
    render(<PlanVivoPanel plan={PLAN} />);
    expect(screen.getByRole("heading", { name: /Dona trabajando/ })).toBeInTheDocument();
    const lista = screen.getByRole("list");
    expect(within(lista).getAllByRole("listitem")).toHaveLength(4);
  });

  it("comunica el estado con texto, no sólo color", () => {
    render(<PlanVivoPanel plan={PLAN} />);
    expect(screen.getByText(/— hecho/)).toBeInTheDocument();
    expect(screen.getByText(/— en curso/)).toBeInTheDocument();
    expect(screen.getByText(/— falló/)).toBeInTheDocument();
    expect(screen.getByText(/— pendiente/)).toBeInTheDocument();
  });

  it("muestra el motivo de un paso fallido", () => {
    render(<PlanVivoPanel plan={PLAN} />);
    expect(screen.getByText("sin destinatario")).toBeInTheDocument();
  });

  it("usa aria-live polite para las actualizaciones", () => {
    render(<PlanVivoPanel plan={PLAN} />);
    expect(screen.getByRole("list")).toHaveAttribute("aria-live", "polite");
  });

  it("el pulso del paso en curso se desactiva con reduced-motion", () => {
    const { container } = render(<PlanVivoPanel plan={PLAN} />);
    const pulso = container.querySelector(".animate-pulse");
    expect(pulso).not.toBeNull();
    expect(pulso?.className).toContain("motion-reduce:animate-none");
  });

  it("las filas de paso son enfocables por teclado", () => {
    render(<PlanVivoPanel plan={PLAN} />);
    for (const li of screen.getAllByRole("listitem")) {
      expect(li).toHaveAttribute("tabindex", "0");
    }
  });
});
