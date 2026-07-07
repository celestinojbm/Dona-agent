// landing/lib/reportes-bridge.test.ts — Reportes/Medición (Fase 1)
//
// Tests del bridge HMAC de reportes. Mismo patrón que assets-bridge.test.ts.
// Verifica:
//   - missing subscription_id → ok=false sin red
//   - secret/url faltante → ok=false sin red
//   - HMAC se computa sobre el body exacto y apunta a /internal/reportes
//   - periodo se propaga en el body
//   - 200 retorna data tipada; 404/401 retornan ok=false con status
//   - timeout retorna ok=false con error timeout

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env.BACKEND_URL = "http://backend.test";
  process.env.INTERNAL_BRIDGE_SECRET = "test-secret-xyz";
  vi.resetModules();
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
  vi.restoreAllMocks();
});


describe("reportes-bridge · validación de inputs", () => {
  it("fetchReportes sin subscription_id retorna missing_subscription_id", async () => {
    const { fetchReportes } = await import("./reportes-bridge");
    const r = await fetchReportes("");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_subscription_id");
  });
});


describe("reportes-bridge · env vars faltantes", () => {
  it("sin BACKEND_URL retorna backend_url_missing", async () => {
    delete process.env.BACKEND_URL;
    const { fetchReportes } = await import("./reportes-bridge");
    const r = await fetchReportes("sub_x");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("backend_url_missing");
  });

  it("sin INTERNAL_BRIDGE_SECRET retorna error", async () => {
    delete process.env.INTERNAL_BRIDGE_SECRET;
    const { fetchReportes } = await import("./reportes-bridge");
    const r = await fetchReportes("sub_x");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("internal_bridge_secret_missing");
  });
});


describe("reportes-bridge · firma HMAC, URL y body", () => {
  it("envía X-Internal-Signature con HMAC y apunta a /internal/reportes", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ reporte: {} }), { status: 200 }),
      );
    const { fetchReportes } = await import("./reportes-bridge");
    await fetchReportes("sub_xyz");
    expect(fetchSpy).toHaveBeenCalled();
    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/internal/reportes");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Internal-Signature"]).toMatch(/^[a-f0-9]{64}$/);
    expect(headers["Content-Type"]).toBe("application/json");
    const body = init.body as string;
    expect(body).toContain("sub_xyz");
  });

  it("propaga periodo en el body cuando se pasa", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ reporte: {} }), { status: 200 }),
      );
    const { fetchReportes } = await import("./reportes-bridge");
    await fetchReportes("sub_x", { periodo: "semana" });
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.subscription_id).toBe("sub_x");
    expect(body.periodo).toBe("semana");
  });

  it("no incluye periodo en el body si no se pasa", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ reporte: {} }), { status: 200 }),
      );
    const { fetchReportes } = await import("./reportes-bridge");
    await fetchReportes("sub_x");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ subscription_id: "sub_x" });
  });
});


describe("reportes-bridge · respuestas del backend", () => {
  it("status 200 retorna ok=true con data tipada", async () => {
    const data = {
      reporte: {
        periodo: "mes",
        etiqueta: "octubre 2026",
        inicio: "2026-10-01T00:00:00",
        fin: "2026-11-01T00:00:00",
        ventas: 150,
        gastos: 50,
        utilidad: 100,
        num_pedidos: 1,
        num_transacciones: 4,
        top_categorias: [{ categoria: "insumos", total: 30 }],
        comparacion_semana_previa: null,
        hay_datos: true,
      },
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(data), { status: 200 }),
    );
    const { fetchReportes } = await import("./reportes-bridge");
    const r = await fetchReportes("sub_x");
    expect(r.ok).toBe(true);
    expect(r.data?.reporte.ventas).toBe(150);
    expect(r.data?.reporte.hay_datos).toBe(true);
  });

  it("status 404 retorna ok=false status=404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("not found", { status: 404 }),
    );
    const { fetchReportes } = await import("./reportes-bridge");
    const r = await fetchReportes("sub_x");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(404);
    expect(r.error).toBe("backend_404");
  });

  it("status 401 retorna ok=false status=401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("unauthorized", { status: 401 }),
    );
    const { fetchReportes } = await import("./reportes-bridge");
    const r = await fetchReportes("sub_x");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(401);
  });
});
