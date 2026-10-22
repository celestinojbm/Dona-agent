// landing/app/api/waitlist/route.test.tsx — Lista de espera abierta en pausa.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authSpy = vi.fn();
const getStripeSpy = vi.fn(() => {
  throw new Error("Stripe no debe usarse");
});
vi.mock("@/auth", () => ({ auth: authSpy }));
vi.mock("@/lib/stripe", () => ({ getStripe: getStripeSpy, PLANS: {}, PAQUETES: {} }));

import { POST } from "./route";
import { normalizarEmail, normalizarTelefono } from "@/lib/lista-espera";

const fetchSpy = vi.fn();

function peticion(cuerpo: unknown): Request {
  return new Request("http://test/api/waitlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof cuerpo === "string" ? cuerpo : JSON.stringify(cuerpo),
  });
}

beforeEach(() => {
  fetchSpy.mockReset();
  fetchSpy.mockResolvedValue(new Response(null, { status: 201 }));
  vi.stubGlobal("fetch", fetchSpy);
  vi.stubEnv("SUPABASE_URL", "https://proyecto.supabase.co/");
  vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", "sb_secret_prueba");
  vi.stubEnv("BACKEND_URL", "http://backend.invalid");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  expect(authSpy).not.toHaveBeenCalled();
  expect(getStripeSpy).not.toHaveBeenCalled();
});

describe("normalización", () => {
  it("email en minúsculas y válido", () => {
    expect(normalizarEmail("  Hola@Ejemplo.COM ")).toBe("hola@ejemplo.com");
    expect(normalizarEmail("sin-arroba")).toBeNull();
    expect(normalizarEmail("a b@c.co")).toBeNull();
    expect(normalizarEmail(`${"a".repeat(250)}@b.co`)).toBeNull();
    expect(normalizarEmail(42)).toBeNull();
  });

  it("teléfono internacional: 7–15 dígitos, + inicial opcional", () => {
    expect(normalizarTelefono("+58 (412) 123-4567")).toBe("+584121234567");
    expect(normalizarTelefono("1234567")).toBe("1234567");
    expect(normalizarTelefono("")).toBeUndefined();
    expect(normalizarTelefono(undefined)).toBeUndefined();
    expect(normalizarTelefono("123456")).toBeNull();
    expect(normalizarTelefono("+1234567890123456")).toBeNull();
    expect(normalizarTelefono("++1234567")).toBeNull();
    expect(normalizarTelefono("12a4567")).toBeNull();
  });
});

describe("POST /api/waitlist", () => {
  it("guarda email y teléfono con upsert por email en Supabase", async () => {
    const res = await POST(peticion({ email: "Ana@Ejemplo.com", phone: "+1 000-000-0000" }));
    expect(res.status).toBe(200);
    expect(res.headers.get("cache-control")).toBe("no-store");
    expect(await res.json()).toEqual({ ok: true });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://proyecto.supabase.co/rest/v1/waitlist_signups?on_conflict=email");
    const headers = init.headers as Record<string, string>;
    expect(headers.apikey).toBe("sb_secret_prueba");
    expect(headers.Authorization).toBeUndefined();
    expect(headers.Prefer).toContain("resolution=merge-duplicates");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "ana@ejemplo.com",
      source: "usadona-pausa",
      phone: "+10000000000",
    });
  });

  it("sin teléfono no lo envía (no borra uno anterior)", async () => {
    const res = await POST(peticion({ email: "ana@ejemplo.com", phone: "" }));
    expect(res.status).toBe(200);
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({
      email: "ana@ejemplo.com",
      source: "usadona-pausa",
    });
  });

  it("clave JWT antigua va también como Bearer", async () => {
    vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", "eyJprueba");
    await POST(peticion({ email: "ana@ejemplo.com" }));
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer eyJprueba");
  });

  it.each([
    [{ email: "no-es-correo" }],
    [{ email: "ana@ejemplo.com", phone: "12" }],
    [{ phone: "+10000000000" }],
    ["no es json"],
    [[1, 2]],
  ])("rechaza datos inválidos %#", async (cuerpo) => {
    const res = await POST(peticion(cuerpo));
    expect(res.status).toBe(400);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rechaza cuerpos demasiado grandes", async () => {
    const res = await POST(peticion({ email: "ana@ejemplo.com", x: "a".repeat(3000) }));
    expect(res.status).toBe(413);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("honeypot: responde ok sin guardar", async () => {
    const res = await POST(peticion({ email: "bot@spam.com", empresa: "ACME" }));
    expect(res.status).toBe(200);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("sin credenciales de servidor responde 503 sin red", async () => {
    vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", "");
    const res = await POST(peticion({ email: "ana@ejemplo.com" }));
    expect(res.status).toBe(503);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("si Supabase falla responde 502", async () => {
    fetchSpy.mockResolvedValue(new Response("{}", { status: 500 }));
    const res = await POST(peticion({ email: "ana@ejemplo.com" }));
    expect(res.status).toBe(502);
  });

  it("nunca llama al backend", async () => {
    await POST(peticion({ email: "ana@ejemplo.com" }));
    for (const [url] of fetchSpy.mock.calls) {
      expect(String(url)).not.toContain("backend.invalid");
    }
  });
});
