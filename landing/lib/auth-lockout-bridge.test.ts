// landing/lib/auth-lockout-bridge.test.ts
// Tests del bridge de lockout (rank 4). Foco: fail-open ante fallos del backend,
// firma HMAC correcta, y best-effort del record.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { checkLoginLockout, recordLoginAttempt } from "./auth-lockout-bridge";

const ENV_ORIGINAL = { ...process.env };

beforeEach(() => {
  process.env.BACKEND_URL = "https://backend.test";
  process.env.INTERNAL_BRIDGE_SECRET = "test-secret";
});

afterEach(() => {
  vi.restoreAllMocks();
  process.env = { ...ENV_ORIGINAL };
});

describe("checkLoginLockout — fail-open", () => {
  it("no-bloqueado si el bridge no está configurado", async () => {
    delete process.env.BACKEND_URL;
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const r = await checkLoginLockout("a@test.com");
    expect(r.bloqueado).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("no-bloqueado si fetch lanza (backend caído)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const r = await checkLoginLockout("a@test.com");
    expect(r.bloqueado).toBe(false);
  });

  it("no-bloqueado ante status != ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500 }),
    );
    const r = await checkLoginLockout("a@test.com");
    expect(r.bloqueado).toBe(false);
  });

  it("propaga bloqueado=true del backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ bloqueado: true, retry_after_segundos: 900 }),
      }),
    );
    const r = await checkLoginLockout("a@test.com");
    expect(r.bloqueado).toBe(true);
    expect(r.retry_after_segundos).toBe(900);
  });

  it("firma con HMAC-SHA256 y pega al path login-check", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ bloqueado: false, retry_after_segundos: 0 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    await checkLoginLockout("a@test.com");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("https://backend.test/internal/auth/login-check");
    expect(opts.headers["X-Internal-Signature"]).toMatch(/^[0-9a-f]{64}$/);
    expect(JSON.parse(opts.body)).toEqual({ email: "a@test.com" });
  });

  it("no llama al backend con email vacío", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const r = await checkLoginLockout("");
    expect(r.bloqueado).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("recordLoginAttempt", () => {
  it("manda email + exito al path login-record", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);
    await recordLoginAttempt("a@test.com", false);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("https://backend.test/internal/auth/login-record");
    expect(JSON.parse(opts.body)).toEqual({ email: "a@test.com", exito: false });
  });

  it("no lanza si el bridge falla (best-effort)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    await expect(recordLoginAttempt("a@test.com", true)).resolves.toBeUndefined();
  });
});
