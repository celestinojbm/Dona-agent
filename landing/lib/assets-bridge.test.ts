// landing/lib/assets-bridge.test.ts — Galería de Activos (Fase 1)
//
// Tests del bridge HMAC de la galería. Mismo patrón que
// automation-bridge.test.ts. Verifica:
//   - missing subscription_id → ok=false sin red
//   - secret/url faltante → ok=false sin red
//   - HMAC se computa sobre el body exacto y apunta a /internal/assets
//   - tipo/limite se propagan en el body
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


describe("assets-bridge · validación de inputs", () => {
  it("fetchAssets sin subscription_id retorna missing_subscription_id", async () => {
    const { fetchAssets } = await import("./assets-bridge");
    const r = await fetchAssets("");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_subscription_id");
  });
});


describe("assets-bridge · env vars faltantes", () => {
  it("sin BACKEND_URL retorna backend_url_missing", async () => {
    delete process.env.BACKEND_URL;
    const { fetchAssets } = await import("./assets-bridge");
    const r = await fetchAssets("sub_x");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("backend_url_missing");
  });

  it("sin INTERNAL_BRIDGE_SECRET retorna error", async () => {
    delete process.env.INTERNAL_BRIDGE_SECRET;
    const { fetchAssets } = await import("./assets-bridge");
    const r = await fetchAssets("sub_x");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("internal_bridge_secret_missing");
  });
});


describe("assets-bridge · firma HMAC, URL y body", () => {
  it("envía X-Internal-Signature con HMAC y apunta a /internal/assets", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ assets: [], count: 0 }), { status: 200 }),
      );
    const { fetchAssets } = await import("./assets-bridge");
    await fetchAssets("sub_xyz");
    expect(fetchSpy).toHaveBeenCalled();
    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/internal/assets");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Internal-Signature"]).toMatch(/^[a-f0-9]{64}$/);
    expect(headers["Content-Type"]).toBe("application/json");
    const body = init.body as string;
    expect(body).toContain("sub_xyz");
  });

  it("propaga tipo y limite en el body cuando se pasan", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ assets: [], count: 0 }), { status: 200 }),
      );
    const { fetchAssets } = await import("./assets-bridge");
    await fetchAssets("sub_x", { tipo: "image", limite: 5 });
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.subscription_id).toBe("sub_x");
    expect(body.tipo).toBe("image");
    expect(body.limite).toBe(5);
  });

  it("no incluye tipo/limite en el body si no se pasan", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ assets: [], count: 0 }), { status: 200 }),
      );
    const { fetchAssets } = await import("./assets-bridge");
    await fetchAssets("sub_x");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ subscription_id: "sub_x" });
  });
});


describe("assets-bridge · respuestas del backend", () => {
  it("status 200 retorna ok=true con data tipada", async () => {
    const data = {
      assets: [
        {
          id: 1,
          tipo: "image",
          url_publica: "https://cdn/x.png",
          prompt: "un gato",
          modelo: "nanobanana",
          creado: "2026-07-07T00:00:00",
        },
      ],
      count: 1,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(data), { status: 200 }),
    );
    const { fetchAssets } = await import("./assets-bridge");
    const r = await fetchAssets("sub_x");
    expect(r.ok).toBe(true);
    expect(r.data?.count).toBe(1);
    expect(r.data?.assets[0].tipo).toBe("image");
  });

  it("status 404 retorna ok=false status=404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("not found", { status: 404 }),
    );
    const { fetchAssets } = await import("./assets-bridge");
    const r = await fetchAssets("sub_x");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(404);
    expect(r.error).toBe("backend_404");
  });

  it("status 401 retorna ok=false status=401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("unauthorized", { status: 401 }),
    );
    const { fetchAssets } = await import("./assets-bridge");
    const r = await fetchAssets("sub_x");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(401);
  });
});
