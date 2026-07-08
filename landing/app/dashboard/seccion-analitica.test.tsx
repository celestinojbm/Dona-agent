/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-analitica.test.tsx
//
// Analítica del negocio: KPIs de /api/reportes (mes + semana), actividad
// de créditos desde dashboard-data, distribución de gastos y resumen de
// acciones. Todos los datos son reales — estos tests fijan que cada bloque
// pinta lo que el backend devuelve y que el empty state no inventa nada.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionAnalitica from "./seccion-analitica";
import type { UsuarioResumen } from "@/lib/dashboard-types";
import type { Reporte } from "@/lib/reportes-types";

const DATA: UsuarioResumen = {
  usuario: { id: "u1", email: "t@x.com", telefono: "1555" },
  creditos: { saldo_actual: 170, creditos_mensuales: 100, ultimo_movimiento: null },
  suscripcion: {
    estado: "active",
    plan: "premium",
    stripe_customer_id: "cus",
    stripe_subscription_id: "sub",
    current_period_end: null,
    cancel_at_period_end: false,
    actualizado: null,
  },
  transacciones_recientes: [
    { delta: -150, razon: "gen_video", saldo_resultante: 170, creado: null },
    { delta: 500, razon: "recarga", saldo_resultante: 320, creado: null },
    { delta: -50, razon: "gen_imagen", saldo_resultante: 270, creado: null },
  ],
  resumen: { puede_cancelar: true, dashboard_ready: true },
};

function reporte(overrides: Partial<Reporte> = {}): Reporte {
  return {
    periodo: "mes",
    etiqueta: "julio 2026",
    inicio: "2026-07-01",
    fin: "2026-07-31",
    ventas: 4500.5,
    gastos: 1200,
    utilidad: 3300.5,
    num_pedidos: 12,
    num_transacciones: 20,
    top_categorias: [
      { categoria: "insumos", total: 800 },
      { categoria: "envíos", total: 400 },
    ],
    hay_datos: true,
    ...overrides,
  };
}

function mockFetch(mes: Reporte, semana: Reporte) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("periodo=mes")) {
        return new Response(JSON.stringify({ reporte: mes }), { status: 200 });
      }
      if (url.includes("periodo=semana")) {
        return new Response(JSON.stringify({ reporte: semana }), { status: 200 });
      }
      if (url.includes("/api/automation/acciones")) {
        return new Response(
          JSON.stringify({
            acciones: [
              { estado: "pending_approval" },
              { estado: "completed" },
              { estado: "completed" },
            ],
          }),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 200 });
    }),
  );
}

beforeEach(() => {
  mockFetch(
    reporte(),
    reporte({
      periodo: "semana",
      etiqueta: "30/06 → 07/07",
      comparacion_semana_previa: { delta_ventas_pct: 12.4 },
      pedidos_entregados: 3,
      pedidos_pendientes: 1,
      num_pedidos: 4,
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SeccionAnalitica · métricas reales", () => {
  it("pinta los KPIs de negocio del mes con el delta semanal", async () => {
    render(<SeccionAnalitica data={DATA} />);
    expect(await screen.findByText(/Ventas/)).toBeInTheDocument();
    expect(screen.getByText(/4,500\.50/)).toBeInTheDocument();
    expect(screen.getByText(/1,200\.00/)).toBeInTheDocument();
    expect(screen.getByText(/\+12\.4% sem\./)).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("muestra la actividad de créditos con recargas y consumo reales", async () => {
    render(<SeccionAnalitica data={DATA} />);
    expect(
      await screen.findByText(/Actividad de créditos/),
    ).toBeInTheDocument();
    // recargado = 500 · consumido = 150 + 50 = 200
    expect(screen.getByText(/Recargas \+500/)).toBeInTheDocument();
    expect(screen.getByText(/Consumo −200/)).toBeInTheDocument();
    expect(screen.getByText("170")).toBeInTheDocument();
  });

  it("lista la distribución de gastos por categoría", async () => {
    render(<SeccionAnalitica data={DATA} />);
    expect(
      await screen.findByText(/Distribución de gastos/),
    ).toBeInTheDocument();
    expect(screen.getByText("insumos")).toBeInTheDocument();
    expect(screen.getByText(/800\.00/)).toBeInTheDocument();
  });

  it("resume las acciones activas e históricas", async () => {
    render(<SeccionAnalitica data={DATA} />);
    expect(await screen.findByText(/Acciones activas/)).toBeInTheDocument();
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText(/2 en historial/)).toBeInTheDocument();
  });

  it("no inventa datos: con hay_datos=false muestra el aviso de vacío", async () => {
    mockFetch(
      reporte({ hay_datos: false, ventas: 0, gastos: 0, utilidad: 0, num_pedidos: 0, top_categorias: [] }),
      reporte({ periodo: "semana", hay_datos: false, ventas: 0, gastos: 0, utilidad: 0, num_pedidos: 0, top_categorias: [] }),
    );
    render(<SeccionAnalitica data={DATA} />);
    expect(
      await screen.findByText(/Aún no hay datos de negocio/),
    ).toBeInTheDocument();
  });
});
