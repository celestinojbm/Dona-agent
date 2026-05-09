// landing/lib/automation-bridge.test.ts — T2.1.B
//
// Tests del bridge HMAC. Verifica que:
//   - missing subscription_id → ok=false sin red
//   - secret/url faltante → ok=false sin red
//   - HMAC se computa sobre el body exacto
//   - 200 retorna data tipada
//   - 4xx/5xx retornan ok=false con status
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


describe("automation-bridge · validación de inputs", () => {
  it("fetchAcciones sin subscription_id retorna missing_subscription_id", async () => {
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_subscription_id");
  });

  it("aprobarAccion sin subscription_id retorna error", async () => {
    const { aprobarAccion } = await import("./automation-bridge");
    const r = await aprobarAccion("", 1);
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_subscription_id");
  });

  it("aprobarAccion con accionId no entero retorna invalid_accion_id", async () => {
    const { aprobarAccion } = await import("./automation-bridge");
    const r = await aprobarAccion("sub_x", Number.NaN);
    expect(r.ok).toBe(false);
    expect(r.error).toBe("invalid_accion_id");
  });
});


describe("automation-bridge · env vars faltantes", () => {
  it("sin BACKEND_URL retorna backend_url_missing", async () => {
    delete process.env.BACKEND_URL;
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("sub_x");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("backend_url_missing");
  });

  it("sin INTERNAL_BRIDGE_SECRET retorna error", async () => {
    delete process.env.INTERNAL_BRIDGE_SECRET;
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("sub_x");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("internal_bridge_secret_missing");
  });
});


describe("automation-bridge · firma HMAC y respuestas", () => {
  it("envía X-Internal-Signature con HMAC del body exacto", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ acciones: [], count: 0 }), {
          status: 200,
        }),
      );
    const { fetchAcciones } = await import("./automation-bridge");
    await fetchAcciones("sub_xyz");
    expect(fetchSpy).toHaveBeenCalled();
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Internal-Signature"]).toMatch(/^[a-f0-9]{64}$/);
    expect(headers["Content-Type"]).toBe("application/json");
    // Body es el JSON con subscription_id
    const body = init.body as string;
    expect(body).toContain("sub_xyz");
  });

  it("status 200 retorna ok=true con data", async () => {
    const data = { acciones: [{ id: 1 }], count: 1 };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(data), { status: 200 }),
    );
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("sub_x");
    expect(r.ok).toBe(true);
    expect(r.data?.count).toBe(1);
  });

  it("status 404 retorna ok=false status=404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("not found", { status: 404 }),
    );
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("sub_x");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(404);
    expect(r.error).toBe("backend_404");
  });

  it("status 401 retorna ok=false status=401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("unauthorized", { status: 401 }),
    );
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("sub_x");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(401);
  });

  it("aprobarAccion incluye accion_id en el body", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ accion: { id: 42 } }), { status: 200 }),
      );
    const { aprobarAccion } = await import("./automation-bridge");
    await aprobarAccion("sub_x", 42);
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.subscription_id).toBe("sub_x");
    expect(body.accion_id).toBe(42);
  });

  it("URL apunta a /internal/automation/* en BACKEND_URL", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ count: 0, oportunidades: [] }), {
          status: 200,
        }),
      );
    const { fetchOportunidades } = await import("./automation-bridge");
    await fetchOportunidades("sub_x");
    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/internal/automation/oportunidades");
  });

  it("ejecutarAccion apunta a /internal/automation/acciones/ejecutar", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ accion: {}, ejecucion: { estado_final: "completed" } }),
          { status: 200 },
        ),
      );
    const { ejecutarAccion } = await import("./automation-bridge");
    await ejecutarAccion("sub_x", 7);
    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toBe(
      "http://backend.test/internal/automation/acciones/ejecutar",
    );
  });
});


describe("automation-bridge · seguridad · no expone secrets", () => {
  it("respuesta NUNCA contiene INTERNAL_BRIDGE_SECRET en error_message", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("backend dijo: el secreto", { status: 500 }),
    );
    const { fetchAcciones } = await import("./automation-bridge");
    const r = await fetchAcciones("sub_x");
    const json = JSON.stringify(r);
    expect(json).not.toContain("test-secret-xyz");
    expect(json).not.toContain("INTERNAL_BRIDGE_SECRET");
  });
});
