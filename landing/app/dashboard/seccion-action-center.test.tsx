/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-action-center.test.tsx
//
// Hotfix T2.1.B: tests de UI para verificar que el componente:
//   - muestra empty state cuando backend retorna lista vacía
//   - muestra empty state cuando hay sub no persistida (route handler
//     ya convierte 404 backend → 200 [])
//   - muestra error real solo ante 4xx/5xx genuinos
//   - mantiene el botón "Generar acciones" en TODOS los estados
//   - botón generar funciona aún cuando lista inicial está vacía/error

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionActionCenter from "./seccion-action-center";

afterEach(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  // jsdom no provee window.alert · stub
  vi.stubGlobal("alert", vi.fn());
});


function mockFetchOnce(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response));
}


describe("SeccionActionCenter · empty state", () => {
  it("backend devuelve lista vacía → muestra empty state con CTA", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [], count: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/Aún no hay acciones generadas/i),
      ).toBeInTheDocument(),
    );
    // Botón en empty state
    const botones = screen.getAllByRole("button", {
      name: /Generar acciones/i,
    });
    expect(botones.length).toBeGreaterThan(0);
  });

  it("subscription_no_persistida → route handler convierte a 200 [] → empty state", async () => {
    // Simulamos lo que el route handler ahora retorna en ese caso
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [], count: 0 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/Aún no hay acciones generadas/i),
      ).toBeInTheDocument(),
    );
  });
});


describe("SeccionActionCenter · error real (5xx)", () => {
  it("502 → muestra error con código + ofrece reintentar y generar", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ error: "backend_unavailable" }), {
        status: 502,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/No pudimos cargar tus acciones/i),
      ).toBeInTheDocument(),
    );
    // Código del error visible
    expect(screen.getByText(/error_502/i)).toBeInTheDocument();
    // Botón Reintentar disponible
    expect(
      screen.getByRole("button", { name: /Reintentar/i }),
    ).toBeInTheDocument();
    // Botón Generar acciones DEBE seguir disponible (en error real
    // también, después del hotfix · al menos uno en la cabecera)
    const botonesGenerar = screen.getAllByRole("button", {
      name: /Generar acciones/i,
    });
    expect(botonesGenerar.length).toBeGreaterThanOrEqual(1);
  });

  it("504 timeout → muestra error con código y opción de reintentar", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ error: "backend_timeout" }), {
        status: 504,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/error_504/i)).toBeInTheDocument(),
    );
  });
});


describe("SeccionActionCenter · loading inicial", () => {
  it("antes de la primera respuesta muestra Cargando…", async () => {
    // Promise nunca se resuelve durante el render
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<SeccionActionCenter />);
    expect(screen.getByText(/Cargando…/i)).toBeInTheDocument();
  });
});


describe("SeccionActionCenter · acciones presentes", () => {
  it("renderiza acción LOW pending con botón Ejecutar (dry-run)", async () => {
    const accion = {
      id: 1,
      opportunity_id: "opp_1",
      playbook_id: "diagnostico_a_plan_semanal",
      tipo_accion: "generar_plan_semanal",
      titulo: "Plan semanal de prueba",
      descripcion: "Genera un plan semanal",
      razon_recomendacion: "Tu diagnóstico está completo",
      estado: "pending",
      riesgo: "low",
      costo_creditos_estimado: 8,
      requires_approval: false,
      result_json: "{}",
      error_message: "",
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T00:00:00Z",
      approved_at: null,
      rejected_at: null,
      completed_at: null,
    };
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/Plan semanal de prueba/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/Bajo/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    ).toBeInTheDocument();
  });

  it("renderiza acción CRITICAL needs_approval con aviso de bloqueo", async () => {
    const accion = {
      id: 2,
      opportunity_id: "",
      playbook_id: "",
      tipo_accion: "envio_masivo_clientes",
      titulo: "Envío masivo prueba",
      descripcion: "Manda mensajes a todos",
      razon_recomendacion: "",
      estado: "needs_approval",
      riesgo: "critical",
      costo_creditos_estimado: 100,
      requires_approval: true,
      result_json: "{}",
      error_message: "",
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T00:00:00Z",
      approved_at: null,
      rejected_at: null,
      completed_at: null,
    };
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/Envío masivo prueba/)).toBeInTheDocument(),
    );
    // Aviso de CRITICAL bloqueada
    expect(
      screen.getByText(/Esta acción es crítica/i),
    ).toBeInTheDocument();
    // Crítico NO ofrece "Aprobar" en T2.1.B
    expect(
      screen.queryByRole("button", { name: /^Aprobar$/i }),
    ).not.toBeInTheDocument();
  });
});
