/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/tour.test.tsx — Paso final del tour: lleva al chat
// dentro de Dona (sin canales externos) y sus botones no compiten en fila.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import TourDashboard, { STEPS, TOUR_STORAGE_KEY } from "./tour";

beforeEach(() => localStorage.removeItem(TOUR_STORAGE_KEY));
afterEach(cleanup);

function irAlUltimoPaso() {
  for (let i = 0; i < STEPS.length - 1; i++) {
    fireEvent.click(screen.getByRole("button", { name: /Siguiente/ }));
  }
}

describe("Tour · paso final", () => {
  it("'Ir al chat' navega al chat y cierra el tour", () => {
    const onIrASeccion = vi.fn();
    render(<TourDashboard habilitado onIrASeccion={onIrASeccion} />);
    irAlUltimoPaso();
    fireEvent.click(screen.getByRole("button", { name: /Ir al chat/ }));
    expect(onIrASeccion).toHaveBeenLastCalledWith("chat");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(localStorage.getItem(TOUR_STORAGE_KEY)).toBe("1");
  });

  it("no hay enlaces externos (wa.me) en el paso final", () => {
    render(<TourDashboard habilitado />);
    irAlUltimoPaso();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Listo/ })).toBeInTheDocument();
  });

  it("botones con zona táctil mínima de 44 px (min-h-11)", () => {
    render(<TourDashboard habilitado />);
    for (const nombre of [/Siguiente/, /Saltar tour/]) {
      const botones = screen.getAllByRole("button", { name: nombre });
      expect(botones.some((b) => /\b(min-h-11|h-11)\b/.test(b.className))).toBe(true);
    }
  });
});
