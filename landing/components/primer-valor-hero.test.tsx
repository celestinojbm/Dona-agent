/**
 * @vitest-environment jsdom
 */
// Tests del home de primer valor (F12): placeholder, chips implementados como
// botones accesibles, callbacks de envío y de chip.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { PrimerValorHero, CHIPS_PRIMER_VALOR } from "./primer-valor-hero";

afterEach(cleanup);

describe("PrimerValorHero", () => {
  it("muestra el input con el placeholder y label accesible", () => {
    render(<PrimerValorHero />);
    const input = screen.getByLabelText("¿Qué quieres lograr hoy?");
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute("placeholder", "¿Qué quieres lograr hoy?");
  });

  it("renderiza sólo los chips implementados como botones", () => {
    render(<PrimerValorHero />);
    for (const chip of CHIPS_PRIMER_VALOR) {
      expect(screen.getByRole("button", { name: chip })).toBeInTheDocument();
    }
  });

  it("dispara onChip al pulsar un chip", () => {
    const onChip = vi.fn();
    render(<PrimerValorHero onChip={onChip} />);
    fireEvent.click(screen.getByRole("button", { name: "Armar seguimiento" }));
    expect(onChip).toHaveBeenCalledWith("Armar seguimiento");
  });

  it("envía el texto al hacer submit", () => {
    const onEnviar = vi.fn();
    render(<PrimerValorHero onEnviar={onEnviar} />);
    const input = screen.getByLabelText("¿Qué quieres lograr hoy?");
    fireEvent.change(input, { target: { value: "quiero un seguimiento" } });
    fireEvent.submit(input.closest("form")!);
    expect(onEnviar).toHaveBeenCalledWith("quiero un seguimiento");
  });

  it("no envía texto vacío", () => {
    const onEnviar = vi.fn();
    render(<PrimerValorHero onEnviar={onEnviar} />);
    const input = screen.getByLabelText("¿Qué quieres lograr hoy?");
    fireEvent.submit(input.closest("form")!);
    expect(onEnviar).not.toHaveBeenCalled();
  });
});
