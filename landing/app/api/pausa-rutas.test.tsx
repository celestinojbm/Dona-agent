// landing/app/api/pausa-rutas.test.tsx — Inventario real de rutas API en pausa.
//
// Recorre TODOS los route.ts bajo app/api (no una lista escrita a mano):
// una ruta nueva sin bloqueo de pausa hace fallar este test. Cada handler
// HTTP exportado debe responder el código de pausa SIN consultar la sesión,
// Stripe ni la red.
//
// Excepciones explícitas (con test propio):
//   - api/auth/[...nextauth]: handlers de NextAuth; authorize rechaza en
//     pausa (lib/auth-pausa.test.ts).
//   - api/webhook: Stripe firmado → acuse sin bridge (webhook/route.test.tsx).
//   - api/engineering/login DELETE: solo borra la cookie del panel.
//   - api/waitlist: lista de espera, abierta a propósito en pausa; no usa
//     Stripe, sesión ni backend (waitlist/route.test.tsx).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const authSpy = vi.fn();
const getStripeSpy = vi.fn(() => {
  throw new Error("Stripe no debe usarse en pausa");
});
const cookiesSpy = vi.fn(() => {
  throw new Error("La cookie no debe leerse en pausa");
});

vi.mock("@/auth", () => ({
  auth: authSpy,
  handlers: { GET: vi.fn(), POST: vi.fn() },
  signIn: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("@/lib/stripe", () => ({
  getStripe: getStripeSpy,
  PLANS: {},
  PAQUETES: {},
}));
vi.mock("next/headers", () => ({ cookies: cookiesSpy, headers: vi.fn() }));

const API_DIR = join(process.cwd(), "app", "api");
const METODOS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;

function rutas(dir: string): string[] {
  return readdirSync(dir).flatMap((nombre) => {
    const p = join(dir, nombre);
    if (statSync(p).isDirectory()) return rutas(p);
    return nombre === "route.ts" ? [p] : [];
  });
}

// Ruta relativa con "/" (estable entre sistemas): "chat/route.ts", etc.
function clave(p: string): string {
  return relative(API_DIR, p).split(sep).join("/");
}

const EXCLUIDAS = new Set([
  "auth/[...nextauth]/route.ts",
  "webhook/route.ts",
  "waitlist/route.ts",
]);
const EXCLUIDOS_METODO = new Set(["engineering/login/route.ts DELETE"]);

function estadoEsperado(ruta: string): number {
  if (ruta.startsWith("whatsapp-webhook/")) return 410;
  if (ruta.startsWith("engineering/")) return 404;
  return 503;
}

const fetchSpy = vi.fn();

beforeEach(() => {
  authSpy.mockClear();
  getStripeSpy.mockClear();
  cookiesSpy.mockClear();
  fetchSpy.mockReset();
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const todas = rutas(API_DIR).map(clave).sort();

describe("inventario de rutas API", () => {
  it("encuentra las rutas reales del repo", () => {
    // Si cambia el inventario, este número obliga a revisar el test.
    expect(todas).toContain("checkout/route.ts");
    expect(todas).toContain("billing-portal/route.ts");
    expect(todas).toContain("whatsapp-webhook/route.ts");
    expect(todas).toContain("waitlist/route.ts");
    expect(todas.length).toBe(21);
  });
});

describe.each(todas.filter((r) => !EXCLUIDAS.has(r)))("en pausa · %s", (ruta) => {
  it("todos sus handlers cortan sin sesión, Stripe ni red", async () => {
    const mod = (await import(/* @vite-ignore */ join(API_DIR, ruta))) as Record<
      string,
      unknown
    >;
    const handlers = METODOS.filter(
      (m) => typeof mod[m] === "function" && !EXCLUIDOS_METODO.has(`${ruta} ${m}`),
    );
    expect(handlers.length).toBeGreaterThan(0);

    for (const metodo of handlers) {
      const req = new Request(`http://test/api/${ruta}`, {
        method: metodo,
        headers: { "Content-Type": "application/json" },
        body: metodo === "GET" ? undefined : JSON.stringify({ plan: "premium", embedded: true }),
      });
      const handler = mod[metodo] as (r: Request, ctx: unknown) => Promise<Response>;
      const res = await handler(req, { params: Promise.resolve({ id: "1" }) });

      expect(res.status, `${metodo} ${ruta}`).toBe(estadoEsperado(ruta));
      expect(res.headers.get("cache-control")).toBe("no-store");
    }

    expect(authSpy).not.toHaveBeenCalled();
    expect(getStripeSpy).not.toHaveBeenCalled();
    expect(cookiesSpy).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("cuerpo de la respuesta de pausa", () => {
  it("checkout responde dona_en_pausa con el aviso", async () => {
    const { POST } = await import("./checkout/route");
    const res = await POST();
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({
      error: "dona_en_pausa",
      mensaje: "Dona está completo. Todas las plazas están ocupadas y por ahora no aceptamos nuevas suscripciones ni compras.",
    });
  });
});
