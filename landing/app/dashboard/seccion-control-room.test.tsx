/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-control-room.test.tsx
//
// MVP interno del Dona Control Room. Render estático: progreso del
// proyecto, agentes, hitos recientes y guardrails.
//
// El componente es server-safe y no hace fetch. Si en el futuro se
// alimenta con datos vivos, esos tests irán aparte.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionControlRoom from "./seccion-control-room";

afterEach(() => {
  cleanup();
});

describe("SeccionControlRoom · render base", () => {
  it("muestra el título 'Dona Control Room'", () => {
    render(<SeccionControlRoom />);
    expect(screen.getByText(/Dona Control Room/i)).toBeInTheDocument();
  });

  it("lista los agentes principales: Hermes, Claude Code, Codex, OpenClaw", () => {
    render(<SeccionControlRoom />);
    expect(screen.getAllByText(/Hermes/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Claude Code/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Codex/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/OpenClaw/).length).toBeGreaterThan(0);
  });

  it("muestra el último hito (PR #48) y el contrato next_required_action", () => {
    render(<SeccionControlRoom />);
    expect(screen.getByText(/PR #48/)).toBeInTheDocument();
    expect(screen.getAllByText(/next_required_action/).length).toBeGreaterThan(0);
  });

  it("incluye al menos un guardrail sobre permisos / acciones reales", () => {
    render(<SeccionControlRoom />);
    expect(
      screen.getByText(/No ejecutar acciones reales sin permiso/i),
    ).toBeInTheDocument();
  });

  it("muestra próximos pasos del roadmap inmediato", () => {
    render(<SeccionControlRoom />);
    expect(screen.getAllByText(/Próximos pasos/i).length).toBeGreaterThan(0);
  });
  it("marca el panel como snapshot interno", () => {
    render(<SeccionControlRoom />);
    expect(screen.getAllByText(/Snapshot 2026-05-24/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Celestino\/Hermes/i)).toBeInTheDocument();
  });

});
