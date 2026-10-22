// landing/lib/login-cupo-bridge.test.ts
// El cupo compartido firma el body y, si el backend no contesta, devuelve
// null (el caller usa memoria). No manda el token.

import crypto from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { consultarCupoLogin } from "./login-cupo-bridge";

const ENV_ORIGINAL = { ...process.env };

beforeEach(() => {
  process.env.BACKEND_URL = "https://backend.test";
  process.env.INTERNAL_BRIDGE_SECRET = "bridge-test";
});

afterEach(() => {
  vi.unstubAllGlobals();
  process.env = { ...ENV_ORIGINAL };
});

describe("consultarCupoLogin", () => {
  it("firma HMAC y no incluye el token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ permitido: false, retry_after_segundos: 900 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const r = await consultarCupoLogin("203.0.113.10", "engineering");
    expect(r).toEqual({ permitido: false, retryAfterSegundos: 900 });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("https://backend.test/internal/panel/login-cupo");
    const esperado = crypto
      .createHmac("sha256", "bridge-test")
      .update(opts.body, "utf8")
      .digest("hex");
    expect(opts.headers["X-Internal-Signature"]).toBe(esperado);
    expect(JSON.parse(opts.body)).toEqual({
      ip: "203.0.113.10",
      usuario: "engineering",
    });
  });

  it("null si el bridge no está configurado (no finge un permitido)", async () => {
    delete process.env.BACKEND_URL;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(await consultarCupoLogin("203.0.113.10", "engineering")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("null si el backend no responde", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    expect(await consultarCupoLogin("203.0.113.10", "engineering")).toBeNull();
  });

  it("null ante status distinto de ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    expect(await consultarCupoLogin("203.0.113.10", "engineering")).toBeNull();
  });

  it("propaga permitido=true sin retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ permitido: true, retry_after_segundos: 0 }),
      }),
    );
    expect(await consultarCupoLogin("203.0.113.10", "engineering")).toEqual({
      permitido: true,
      retryAfterSegundos: 0,
    });
  });
});
