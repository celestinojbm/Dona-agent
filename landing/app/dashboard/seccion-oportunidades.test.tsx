/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-oportunidades.test.tsx
//
// Vista de oportunidades detectadas. Verifica que el componente:
//   - renderiza oportunidades con impacto, riesgo, razón y playbook
//   - muestra empty state cuando el perfil está listo pero no hay nada
//   - explica el diagnóstico incompleto (contrato perfil_*)
//   - muestra error real solo ante 4xx/5xx genuinos + reintento

import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionOportunidades from "./seccion-oportunidades";
import type { OportunidadDetectada } from "@/lib/automation-types";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function mockFetchOnce(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response));
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const OPORTUNIDAD_BASE: OportunidadDetectada = {
  id: "opp-reactivacion-1",
  tipo: "reactivacion_clientes",
  titulo: "Reactivar clientes inactivos",
  descripcion:
    "Tienes 14 clientes sin compras en 60 días; una campaña de reactivación puede recuperarlos.",
  razon: "El 30% de tu cartera lleva más de 2 meses sin actividad.",
  prioridad: 1,
  impacto_estimado: "alto",
  riesgo: "medium",
  fuente_datos: ["crm", "finanzas"],
  playbook_sugerido: "reactivacion-clientes",
};

describe("SeccionOportunidades · render con datos", () => {
  it("muestra título, impacto, riesgo, razón, fuentes y playbook", async () => {
    mockFetchOnce(
      jsonResponse({
        oportunidades: [OPORTUNIDAD_BASE],
        count: 1,
        perfil_estado: "ready",
      }),
    );
    render(<SeccionOportunidades />);
    await waitFor(() =>
      expect(
        screen.getByText(/Reactivar clientes inactivos/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/Impacto alto/i)).toBeInTheDocument();
    expect(screen.getByText(/Riesgo medio/i)).toBeInTheDocument();
    expect(screen.getByText(/Por qué ahora:/i)).toBeInTheDocument();
    expect(screen.getByText("crm")).toBeInTheDocument();
    expect(screen.getByText("finanzas")).toBeInTheDocument();
    expect(screen.getByText(/reactivacion-clientes/)).toBeInTheDocument();
    expect(
      screen.getByText(/1 oportunidades detectadas/i),
    ).toBeInTheDocument();
  });
});

describe("SeccionOportunidades · empty state", () => {
  it("perfil listo sin oportunidades → empty state sin panel de diagnóstico", async () => {
    mockFetchOnce(
      jsonResponse({
        oportunidades: [],
        count: 0,
        perfil_estado: "ready",
      }),
    );
    render(<SeccionOportunidades />);
    await waitFor(() =>
      expect(
        screen.getByText(/No detectamos oportunidades nuevas/i),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/campos completados/i)).not.toBeInTheDocument();
  });

  it("respuesta sin perfil_estado (payload legacy) → empty state simple", async () => {
    mockFetchOnce(jsonResponse({ oportunidades: [], count: 0 }));
    render(<SeccionOportunidades />);
    await waitFor(() =>
      expect(
        screen.getByText(/No detectamos oportunidades nuevas/i),
      ).toBeInTheDocument(),
    );
  });
});

describe("SeccionOportunidades · diagnóstico incompleto", () => {
  it("perfil incomplete → muestra razón, progreso y siguiente paso", async () => {
    mockFetchOnce(
      jsonResponse({
        oportunidades: [],
        count: 0,
        perfil_estado: "incomplete",
        perfil_campos_llenos: 2,
        perfil_campos_totales: 6,
        perfil_razon: "Tu diagnóstico está a medias.",
        perfil_siguiente_paso:
          "Escribe 'continuar diagnóstico' a Dona por WhatsApp.",
      }),
    );
    render(<SeccionOportunidades />);
    await waitFor(() =>
      expect(
        screen.getByText(/Tu diagnóstico está a medias/i),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/2 de 6 campos completados/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/continuar diagnóstico/i),
    ).toBeInTheDocument();
    // El empty state genérico NO se muestra a la vez que el diagnóstico
    expect(
      screen.queryByText(/No detectamos oportunidades nuevas/i),
    ).not.toBeInTheDocument();
  });
});

describe("SeccionOportunidades · error real (5xx)", () => {
  it("502 → muestra código de error y botón Reintentar recarga", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ error: "backend_unavailable" }, 502),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          oportunidades: [OPORTUNIDAD_BASE],
          count: 1,
          perfil_estado: "ready",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<SeccionOportunidades />);
    await waitFor(() =>
      expect(
        screen.getByText(/No pudimos cargar tus oportunidades/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/error_502/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Reintentar/i }));
    await waitFor(() =>
      expect(
        screen.getByText(/Reactivar clientes inactivos/i),
      ).toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("fetch lanza excepción → network_error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValueOnce(new Error("boom")),
    );
    render(<SeccionOportunidades />);
    await waitFor(() =>
      expect(screen.getByText(/network_error/)).toBeInTheDocument(),
    );
  });
});
