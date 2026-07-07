import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

// SEC-WEB-05 (Fase 0): el proxy GET reenviaba TODOS los headers del cliente
// (Object.fromEntries(request.headers)) hacia dona-agent.onrender.com,
// incluidas cookies de sesión del dominio landing (ej. la cookie httpOnly
// de /engineering) y headers internos x-vercel-*. Este test verifica que
// el allowlist explícito no reenvía Cookie/Authorization, pero el proxy
// sigue funcionando para el caso legítimo (verificación GET de Meta).

import { GET, POST } from "./route";

function buildFetchMock(status = 200, body: unknown = { ok: true }) {
  return vi.fn().mockResolvedValue({
    status,
    json: async () => body,
  });
}

describe("GET /api/whatsapp-webhook (proxy hacia Render)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("no reenvía Cookie ni Authorization ni headers x-vercel-*", async () => {
    const fetchMock = buildFetchMock();
    vi.stubGlobal("fetch", fetchMock);

    const req = new NextRequest(
      "http://test/api/whatsapp-webhook?hub.mode=subscribe&hub.verify_token=tok&hub.challenge=123",
      {
        headers: {
          Cookie: "engineering_session=secreto",
          Authorization: "Bearer secreto-privado",
          "x-vercel-id": "abc123",
          "x-vercel-ip-country": "US",
        },
      }
    );

    await GET(req);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const forwardedHeaders = init.headers as Record<string, string>;

    expect(forwardedHeaders.Cookie).toBeUndefined();
    expect(forwardedHeaders.Authorization).toBeUndefined();
    expect(forwardedHeaders["x-vercel-id"]).toBeUndefined();
    expect(forwardedHeaders["x-vercel-ip-country"]).toBeUndefined();
  });

  it("sigue funcionando para el caso legítimo: reenvía query params y responde el JSON del backend", async () => {
    const fetchMock = buildFetchMock(200, { "hub.challenge": "123" });
    vi.stubGlobal("fetch", fetchMock);

    const req = new NextRequest(
      "http://test/api/whatsapp-webhook?hub.mode=subscribe&hub.verify_token=tok&hub.challenge=123"
    );

    const res = await GET(req);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("hub.mode=subscribe");
    expect(String(url)).toContain("hub.verify_token=tok");
    expect(String(url)).toContain("hub.challenge=123");
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ "hub.challenge": "123" });
  });

  it("incluye Content-Type en el allowlist mínimo", async () => {
    const fetchMock = buildFetchMock();
    vi.stubGlobal("fetch", fetchMock);

    const req = new NextRequest("http://test/api/whatsapp-webhook");
    await GET(req);

    const [, init] = fetchMock.mock.calls[0];
    const forwardedHeaders = init.headers as Record<string, string>;
    expect(forwardedHeaders["Content-Type"]).toBe("application/json");
  });
});

describe("POST /api/whatsapp-webhook (proxy hacia Render)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("no reenvía Cookie ni Authorization, pero sí la firma HMAC de Meta", async () => {
    const fetchMock = buildFetchMock();
    vi.stubGlobal("fetch", fetchMock);

    const req = new NextRequest("http://test/api/whatsapp-webhook", {
      method: "POST",
      headers: {
        Cookie: "engineering_session=secreto",
        Authorization: "Bearer secreto-privado",
        "X-Hub-Signature-256": "sha256=firma-valida",
      },
      body: JSON.stringify({ entry: [] }),
    });

    await POST(req);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const forwardedHeaders = init.headers as Record<string, string>;

    expect(forwardedHeaders.Cookie).toBeUndefined();
    expect(forwardedHeaders.Authorization).toBeUndefined();
    expect(forwardedHeaders["X-Hub-Signature-256"]).toBe("sha256=firma-valida");
    expect(forwardedHeaders["Content-Type"]).toBe("application/json");
  });
});
