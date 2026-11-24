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

function req(cuerpo: unknown, tipo = "application/json", extra: Record<string, string> = {}) {
  return new Request("http://localhost/api/lista-espera", {
    method: "POST",
    headers: { "content-type": tipo, ...extra },
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
    expect(init.body).toBe(JSON.stringify({ email: "ana@negocio.com", ip: "" }));
    const firma = crypto.createHmac("sha256", SECRET).update(init.body).digest("hex");
    expect(init.headers["X-Internal-Signature"]).toBe(firma);
    expect(authSpy).not.toHaveBeenCalled();
  });

  it("manda la IP del visitante dentro del cuerpo firmado (límite por IP)", async () => {
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(req({ email: "ana@negocio.com" }, "application/json", { "x-real-ip": "203.0.113.7" }));
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(
      req({ email: "ana@negocio.com" }, "application/json", {
        "x-forwarded-for": "198.51.100.9, 10.0.0.1",
      }),
    );
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(req({ email: "ana@negocio.com" }, "application/json", { "x-real-ip": "1".repeat(80) }));

    const ips = fetchSpy.mock.calls.map(([, init]) => JSON.parse(init.body).ip);
    expect(ips).toEqual(["203.0.113.7", "198.51.100.9", ""]);
    const [, init] = fetchSpy.mock.calls[0];
    const firma = crypto.createHmac("sha256", SECRET).update(init.body).digest("hex");
    expect(init.headers["X-Internal-Signature"]).toBe(firma);
  });

  it("detrás de Cloudflare usa cf-connecting-ip, no la IP del borde", async () => {
    // usadona.com va por Cloudflare: Vercel ve la IP del borde (104.16.0.0/13).
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(
      req({ email: "ana@negocio.com" }, "application/json", {
        "x-real-ip": "104.23.1.2",
        "cf-connecting-ip": "203.0.113.7",
      }),
    );
    // Borde IPv6 de Cloudflare con visitante IPv6.
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(
      req({ email: "ana@negocio.com" }, "application/json", {
        "x-forwarded-for": "2606:4700::1",
        "cf-connecting-ip": "2001:db8::5",
      }),
    );
    // Borde de Cloudflare sin cabecera válida: se queda con la IP del borde.
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(
      req({ email: "ana@negocio.com" }, "application/json", {
        "x-real-ip": "104.23.1.2",
        "cf-connecting-ip": "no-es-una-ip",
      }),
    );

    const ips = fetchSpy.mock.calls.map(([, init]) => JSON.parse(init.body).ip);
    expect(ips).toEqual(["203.0.113.7", "2001:db8::5", "104.23.1.2"]);
  });

  it("ignora cf-connecting-ip si quien conecta no es Cloudflare (acceso directo a vercel.app)", async () => {
    backendResponde(200, { estado: "en_espera", nuevo: true });
    await alta(
      req({ email: "ana@negocio.com" }, "application/json", {
        "x-real-ip": "198.51.100.9",
        "cf-connecting-ip": "203.0.113.99",
      }),
    );
    expect(JSON.parse(fetchSpy.mock.calls[0][1].body).ip).toBe("198.51.100.9");
  });

  it("traduce el 429 del backend (límite por IP o global)", async () => {
    backendResponde(429, { detail: "demasiados_intentos" });
    const r = await alta(req({ email: "ana@negocio.com" }));
    expect(r.status).toBe(429);
    expect(await r.json()).toEqual({ ok: false, error: "demasiados_intentos" });
  });

  it("no revela si un correo ya canjeó una invitación", async () => {
    backendResponde(200, { estado: "invitado", nuevo: false });
    const r = await alta(req({ email: "ajeno@negocio.com" }));
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ ok: true, estado: "en_espera" });
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
    const r = await invitacion(
      req({ email: "ana@negocio.com", codigo: "7KQ2-M9XW-4HTB-RZ8D" }, "application/json", {
        "x-real-ip": "203.0.113.7",
      }),
    );
    expect(await r.json()).toEqual({ ok: true, estado: "invitado" });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("https://backend.example.com/internal/lista-espera/invitacion");
    expect(JSON.parse(init.body)).toEqual({
      email: "ana@negocio.com",
      codigo: "7KQ2-M9XW-4HTB-RZ8D",
      ip: "203.0.113.7",
    });
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
