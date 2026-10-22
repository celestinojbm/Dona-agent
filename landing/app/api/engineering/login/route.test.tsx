// landing/app/api/engineering/login/route.test.tsx
//
// Cupo del POST /api/engineering/login con la pausa apagada (el corte en
// pausa lo cubre pausa-rutas.test.tsx). No hay red ni base de datos.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/pausa", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/pausa")>()),
  DONA_EN_PAUSA: false,
}));

const setCookie = vi.hoisted(() => vi.fn());
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ set: setCookie, delete: vi.fn() })),
}));

import { DELETE, POST } from "./route";
import { fijarReloj, reiniciarCupos } from "@/lib/rate-limit";

const TOKEN = "token-secreto-del-dueno";
const ENV_ORIGINAL = { ...process.env };
let ahora = 5_000_000;

function post(token: unknown, ip: string, raw?: string): Request {
  return new Request("http://test/api/engineering/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-vercel-forwarded-for": ip,
    },
    body: raw ?? JSON.stringify({ token }),
  });
}

beforeEach(() => {
  ahora = 5_000_000;
  fijarReloj(() => ahora);
  reiniciarCupos();
  setCookie.mockClear();
  process.env.PANEL_INGENIERIA_TOKEN = TOKEN;
  delete process.env.RATE_LIMIT_LOGIN_MAX;
  delete process.env.RATE_LIMIT_LOGIN_WINDOW_SECONDS;
});

afterEach(() => {
  fijarReloj(null);
  reiniciarCupos();
  process.env = { ...ENV_ORIGINAL };
});

describe("POST /api/engineering/login · cupo", () => {
  it("el sexto intento responde 429 con Retry-After y no abre sesión", async () => {
    const ip = "203.0.113.10";
    for (let i = 0; i < 5; i++) {
      const r = await POST(post("incorrecto", ip));
      expect(r.status).toBe(401);
    }
    const sexto = await POST(post(TOKEN, ip));
    const cuerpo = await sexto.json();
    expect(sexto.status).toBe(429);
    expect(cuerpo).toEqual({ error: "rate_limit_excedido" });
    expect(sexto.headers.get("retry-after")).toBe("900");
    expect(sexto.headers.get("cache-control")).toBe("no-store");
    expect(setCookie).not.toHaveBeenCalled();
    const texto = JSON.stringify(cuerpo);
    expect(texto).not.toContain("invalid_token");
    expect(texto).not.toContain(TOKEN);
  });

  it("la ventana se reabre y entonces el token correcto entra", async () => {
    const ip = "203.0.113.11";
    for (let i = 0; i < 5; i++) await POST(post("incorrecto", ip));
    expect((await POST(post(TOKEN, ip))).status).toBe(429);
    ahora += 900 * 1000;
    const r = await POST(post(TOKEN, ip));
    expect(r.status).toBe(200);
    expect(await r.json()).toEqual({ ok: true });
    expect(setCookie).toHaveBeenCalledOnce();
  });

  it("otra IP no hereda el cupo del mismo usuario del panel", async () => {
    const ipA = "203.0.113.12";
    for (let i = 0; i < 5; i++) await POST(post("incorrecto", ipA));
    expect((await POST(post("incorrecto", ipA))).status).toBe(429);
    const otra = await POST(post("incorrecto", "203.0.113.13"));
    expect(otra.status).toBe(401);
    expect(await otra.json()).toEqual({ error: "invalid_token" });
  });

  it("el 429 es idéntico con token correcto, incorrecto o panel sin configurar", async () => {
    async function agotar(ip: string, token: unknown): Promise<Response> {
      for (let i = 0; i < 5; i++) await POST(post("incorrecto", ip));
      return POST(post(token, ip));
    }

    const conSecreto = await agotar("203.0.113.20", TOKEN);
    const mal = await agotar("203.0.113.21", "otro-token");
    delete process.env.PANEL_INGENIERIA_TOKEN;
    const sinConfig = await agotar("203.0.113.22", TOKEN);

    const firmas = await Promise.all(
      [conSecreto, mal, sinConfig].map(async (r) => ({
        status: r.status,
        body: await r.json(),
        retry: r.headers.get("retry-after"),
      })),
    );
    expect(firmas[0]).toEqual(firmas[1]);
    expect(firmas[1]).toEqual(firmas[2]);
    expect(firmas[0].status).toBe(429);
    expect(JSON.stringify(firmas[0].body)).not.toMatch(/exist|not found|invalid_token/i);
  });

  it("DELETE no consume el cupo del login", async () => {
    for (let i = 0; i < 8; i++) {
      const r = await DELETE();
      expect(r.status).toBe(200);
    }
    const login = await POST(post("incorrecto", "203.0.113.30"));
    expect(login.status).toBe(401);
  });
});
