// landing/app/api/lista-espera/route.test.tsx — Rutas de la lista de espera.
//
// Validan antes de llamar al backend, firman con HMAC el cuerpo exacto que
// envían, no tocan la sesión ni Stripe, y traducen los errores del backend
// sin filtrar detalles internos.

import crypto from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const authSpy = vi.fn();
vi.mock("@/auth", () => ({ auth: authSpy }));

import { POST as alta } from "./route";
import { POST as invitacion } from "./invitacion/route";

const SECRET = "secreto-de-prueba-lista";
const fetchSpy = vi.fn();

function req(cuerpo: unknown, tipo = "application/json") {
  return new Request("http://localhost/api/lista-espera", {
    method: "POST",
    headers: { "content-type": tipo },
    body: typeof cuerpo === "string" ? cuerpo : JSON.stringify(cuerpo),
  });
}

function backendResponde(status: number, cuerpo: unknown) {
  fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify(cuerpo), { status }));
}

beforeEach(() => {
  vi.stubEnv("BACKEND_URL", "https://backend.example.com");
  vi.stubEnv("INTERNAL_BRIDGE_SECRET", SECRET);
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  fetchSpy.mockReset();
  authSpy.mockReset();
});

describe("POST /api/lista-espera", () => {
  it("registra un correo válido con firma HMAC del cuerpo enviado", async () => {
    backendResponde(200, { estado: "en_espera", nuevo: true });
    const r = await alta(req({ email: " ana@negocio.com " }));
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ ok: true, estado: "en_espera" });

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("https://backend.example.com/internal/lista-espera");
    expect(init.body).toBe(JSON.stringify({ email: "ana@negocio.com" }));
    const firma = crypto.createHmac("sha256", SECRET).update(init.body).digest("hex");
    expect(init.headers["X-Internal-Signature"]).toBe(firma);
    expect(authSpy).not.toHaveBeenCalled();
  });

  it("rechaza correos inválidos y cuerpos no JSON sin llamar al backend", async () => {
    expect((await alta(req({ email: "sin-arroba" }))).status).toBe(400);
    expect((await alta(req("email=a@b.com", "application/x-www-form-urlencoded"))).status).toBe(400);
    expect((await alta(req("{no json"))).status).toBe(400);
    expect((await alta(req({ email: "a@b.com", relleno: "x".repeat(3000) }))).status).toBe(400);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("el campo trampa responde 200 sin guardar nada", async () => {
    const r = await alta(req({ email: "bot@spam.com", empresa: "Spam SA" }));
    expect(r.status).toBe(200);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("backend caído o sin configurar → 503 sin detalles internos", async () => {
    fetchSpy.mockRejectedValueOnce(new Error("ECONNREFUSED 10.0.0.1"));
    const r = await alta(req({ email: "ana@negocio.com" }));
    expect(r.status).toBe(503);
    expect(await r.json()).toEqual({ ok: false, error: "no_disponible" });

    vi.stubEnv("INTERNAL_BRIDGE_SECRET", "");
    expect((await alta(req({ email: "ana@negocio.com" }))).status).toBe(503);
  });
});

describe("POST /api/lista-espera/invitacion", () => {
  it("código válido → invitado", async () => {
    backendResponde(200, { estado: "invitado" });
    const r = await invitacion(req({ email: "ana@negocio.com", codigo: "DONA-PILOTO-2026" }));
    expect(await r.json()).toEqual({ ok: true, estado: "invitado" });
    expect(fetchSpy.mock.calls[0][0]).toBe(
      "https://backend.example.com/internal/lista-espera/invitacion",
    );
  });

  it("código corto se rechaza sin llamar al backend", async () => {
    const r = await invitacion(req({ email: "ana@negocio.com", codigo: "abc" }));
    expect(r.status).toBe(403);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("traduce 403 y 429 del backend", async () => {
    backendResponde(403, { detail: "codigo_invalido" });
    expect((await invitacion(req({ email: "a@negocio.com", codigo: "OTRO-CODIGO" }))).status).toBe(403);
    backendResponde(429, { detail: "demasiados_intentos" });
    const r = await invitacion(req({ email: "a@negocio.com", codigo: "OTRO-CODIGO" }));
    expect(r.status).toBe(429);
    expect(await r.json()).toEqual({ ok: false, error: "demasiados_intentos" });
  });
});
