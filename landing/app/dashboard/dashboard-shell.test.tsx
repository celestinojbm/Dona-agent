/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/dashboard-shell.test.tsx
//
// Shell del dashboard (sidebar + secciones + URL sync). Cubre:
//   - navegación: sidebar con secciones, pill activa, cambio de sección
//   - deep-link: ?s=chat monta la sección Chat
//   - badge de acciones pendientes (estados no terminales)
//   - gates: Control Room solo allowlist; acciones/oportunidades fuera
//     con sub cancelada
// Los fetch se mockean por URL; el tour se marca "visto" en localStorage
// para que su modal no interfiera con las queries.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import { act } from "react";
import "@testing-library/jest-dom/vitest";
import DashboardClient from "./dashboard-client";
import { TOUR_STORAGE_KEY } from "./tour";
import type { UsuarioResumen } from "@/lib/dashboard-types";

vi.mock("next-auth/react", () => ({
  signOut: vi.fn(),
}));

const RESUMEN_BASE: UsuarioResumen = {
  usuario: { id: "u1", email: "test@example.com", telefono: "1555000" },
  creditos: {
    saldo_actual: 170,
    creditos_mensuales: 100,
    ultimo_movimiento: null,
  },
  suscripcion: {
    estado: "active",
    plan: "premium",
    stripe_customer_id: "cus_x",
    stripe_subscription_id: "sub_x",
    current_period_end: null,
    cancel_at_period_end: false,
    actualizado: null,
  },
  transacciones_recientes: [
    { delta: -150, razon: "gen_video (150cr)", saldo_resultante: 170, creado: null },
    { delta: 500, razon: "recarga", saldo_resultante: 320, creado: null },
  ],
  resumen: { puede_cancelar: true, dashboard_ready: true },
};

/** Mock de fetch por URL: dashboard-data + acciones (2 activas, 1 terminal). */
function mockFetch(resumen: UsuarioResumen = RESUMEN_BASE) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/dashboard-data")) {
        return new Response(JSON.stringify(resumen), { status: 200 });
      }
      if (url.includes("/api/automation/acciones")) {
        return new Response(
          JSON.stringify({
            acciones: [
              { estado: "pending_approval" },
              { estado: "approved" },
              { estado: "completed" },
            ],
            count: 3,
          }),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 200 });
    }),
  );
}

const SESSION = { user: { email: "test@example.com" } };
const SESSION_INTERNA = { user: { email: "celestinojbm@gmail.com" } };

beforeEach(() => {
  window.localStorage.setItem(TOUR_STORAGE_KEY, "1");
  window.history.replaceState(null, "", "/dashboard");
  mockFetch();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("DashboardShell · sidebar y navegación", () => {
  it("muestra las secciones principales en la sidebar tras cargar", async () => {
    render(<DashboardClient session={SESSION} />);
    const nav = await screen.findAllByRole("navigation", {
      name: /secciones del dashboard/i,
    });
    expect(nav.length).toBeGreaterThan(0);
    for (const label of [
      "Inicio",
      "Chat",
      "Analítica",
      "Outputs",
      "Reportes",
      "Créditos y plan",
      "Integraciones",
    ]) {
      expect(
        (await screen.findAllByRole("button", { name: new RegExp(label, "i") }))
          .length,
      ).toBeGreaterThan(0);
    }
    // Con la sub activa, Acciones y Oportunidades aparecen al estar ready.
    expect(
      (await screen.findAllByRole("button", { name: /Acciones/i })).length,
    ).toBeGreaterThan(0);
    expect(
      (await screen.findAllByRole("button", { name: /Oportunidades/i })).length,
    ).toBeGreaterThan(0);
  });

  it("arranca en Inicio y navega a Créditos y plan actualizando la URL", async () => {
    render(<DashboardClient session={SESSION} />);
    // Inicio: saludo del resumen
    expect(await screen.findByText(/esperan tu aprobación|esto es lo que pasa/i)).toBeInTheDocument();

    const [botonCreditos] = await screen.findAllByRole("button", {
      name: /Créditos y plan/i,
    });
    await act(async () => {
      botonCreditos.click();
    });

    expect(await screen.findByText(/Saldo actual/i)).toBeInTheDocument();
    expect(window.location.search).toContain("s=creditos");
  });

  it("muestra el badge con las acciones pendientes (no terminales)", async () => {
    render(<DashboardClient session={SESSION} />);
    // 3 acciones mock: pending_approval + approved activas, completed terminal → 2
    await waitFor(() => {
      expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    });
  });

  it("respeta el deep-link ?s=chat", async () => {
    window.history.replaceState(null, "", "/dashboard?s=chat");
    render(<DashboardClient session={SESSION} />);
    expect(
      (await screen.findAllByText(/Chat con Dona/i)).length,
    ).toBeGreaterThan(0);
    expect(
      await screen.findByPlaceholderText(/Escríbele a Dona/i),
    ).toBeInTheDocument();
  });
});

describe("DashboardShell · gates", () => {
  it("oculta Control Room para emails fuera de la allowlist", async () => {
    render(<DashboardClient session={SESSION} />);
    await screen.findAllByRole("button", { name: /Inicio/i });
    expect(
      screen.queryByRole("button", { name: /Control Room/i }),
    ).not.toBeInTheDocument();
  });

  it("muestra Control Room (marcado interno) para la allowlist", async () => {
    render(<DashboardClient session={SESSION_INTERNA} />);
    expect(
      (await screen.findAllByRole("button", { name: /Control Room/i })).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/interno/i).length).toBeGreaterThan(0);
  });

  it("apaga Acciones y Oportunidades con suscripción cancelada", async () => {
    mockFetch({
      ...RESUMEN_BASE,
      suscripcion: { ...RESUMEN_BASE.suscripcion, estado: "canceled" },
    });
    render(<DashboardClient session={SESSION} />);
    await screen.findAllByText(/esto es lo que pasa/i);
    expect(
      screen.queryByRole("button", { name: /^Acciones$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Oportunidades/i }),
    ).not.toBeInTheDocument();
  });
});
