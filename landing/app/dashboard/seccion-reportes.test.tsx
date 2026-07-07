/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-reportes.test.tsx
//
// Vista de Reportes/Medición. Verifica que el componente:
//   - renderiza ventas, gastos, utilidad, pedidos y top categorías
//   - muestra empty state con gracia cuando hay_datos=false
//   - muestra la comparación vs. semana previa
//   - muestra error real ante 4xx/5xx + reintento

import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionReportes from "./seccion-reportes";
import type { Reporte } from "@/lib/reportes-types";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const REPORTE_MES: Reporte = {
  periodo: "mes",
  etiqueta: "octubre 2026",
  año: 2026,
  mes: 10,
  inicio: "2026-10-01T00:00:00",
  fin: "2026-11-01T00:00:00",
  ventas: 1500,
  gastos: 500,
  utilidad: 1000,
  num_pedidos: 3,
  num_transacciones: 8,
  top_categorias: [
    { categoria: "insumos", total: 300 },
    { categoria: "renta", total: 200 },
  ],
  comparacion_semana_previa: null,
  hay_datos: true,
};

const REPORTE_VACIO: Reporte = {
  periodo: "mes",
  etiqueta: "octubre 2026",
  inicio: "2026-10-01T00:00:00",
  fin: "2026-11-01T00:00:00",
  ventas: 0,
  gastos: 0,
  utilidad: 0,
  num_pedidos: 0,
  num_transacciones: 0,
  top_categorias: [],
  comparacion_semana_previa: null,
  hay_datos: false,
};

describe("SeccionReportes · render con datos", () => {
  it("muestra ventas, gastos, utilidad, pedidos y top categorías", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(jsonResponse({ reporte: REPORTE_MES })),
    );
    render(<SeccionReportes />);
    await waitFor(() =>
      expect(screen.getByText("Ventas")).toBeInTheDocument(),
    );
    expect(screen.getByText("Gastos")).toBeInTheDocument();
    expect(screen.getByText("Utilidad")).toBeInTheDocument();
    // Montos formateados
    expect(screen.getByText(/1,500\.00/)).toBeInTheDocument();
    expect(screen.getByText(/1,000\.00/)).toBeInTheDocument();
    // Pedidos
    expect(screen.getByText(/3 pedidos/i)).toBeInTheDocument();
    // Top categorías
    expect(screen.getByText("insumos")).toBeInTheDocument();
    expect(screen.getByText("renta")).toBeInTheDocument();
  });
});

describe("SeccionReportes · empty state", () => {
  it("hay_datos=false → empty state con gracia", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(jsonResponse({ reporte: REPORTE_VACIO })),
    );
    render(<SeccionReportes />);
    await waitFor(() =>
      expect(
        screen.getByText(/Aún no hay datos de negocio registrados/i),
      ).toBeInTheDocument(),
    );
    // No muestra tarjetas de métricas
    expect(screen.queryByText("Ventas")).not.toBeInTheDocument();
  });
});

describe("SeccionReportes · comparación semanal", () => {
  it("muestra el delta vs. semana previa cuando viene", async () => {
    const semanaConComparacion: Reporte = {
      ...REPORTE_MES,
      periodo: "semana",
      etiqueta: "30/06 → 07/07",
      pedidos_entregados: 2,
      pedidos_pendientes: 1,
      comparacion_semana_previa: { delta_ventas_pct: 25.5 },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({ reporte: semanaConComparacion }),
        ),
    );
    render(<SeccionReportes />);
    await waitFor(() =>
      expect(
        screen.getByText(/\+25\.5% vs\. semana pasada/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/2 entregados/i)).toBeInTheDocument();
  });
});

describe("SeccionReportes · error real", () => {
  it("502 → muestra código y botón Reintentar recarga", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ error: "backend_unavailable" }, 502))
      .mockResolvedValueOnce(jsonResponse({ reporte: REPORTE_MES }));
    vi.stubGlobal("fetch", fetchMock);

    render(<SeccionReportes />);
    await waitFor(() =>
      expect(
        screen.getByText(/No pudimos cargar tus reportes/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/error_502/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Reintentar/i }));
    await waitFor(() => expect(screen.getByText("Ventas")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("fetch lanza excepción → network_error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new Error("boom")));
    render(<SeccionReportes />);
    await waitFor(() =>
      expect(screen.getByText(/network_error/)).toBeInTheDocument(),
    );
  });
});
