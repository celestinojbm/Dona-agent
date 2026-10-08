// landing/app/api/checkout/route.test.tsx — Checkout en pausa.
//
// La ruta ya no crea sesiones de Stripe: ni suscripción (embebida u
// hospedada, con price ID o price_data inline) ni top-ups. Stripe, la sesión
// y el backend van mockeados para comprobar que NO se tocan.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const sessionsCreate = vi.fn();
const getStripe = vi.fn(() => ({ checkout: { sessions: { create: sessionsCreate } } }));
const auth = vi.fn();
const fetchUsuarioResumen = vi.fn();

vi.mock("@/lib/stripe", () => ({ getStripe, PLANS: {}, PAQUETES: {} }));
vi.mock("@/auth", () => ({ auth }));
vi.mock("@/lib/internal-bridge", () => ({ fetchUsuarioResumen }));

import { POST } from "./route";

beforeEach(() => {
  sessionsCreate.mockReset();
  getStripe.mockClear();
  auth.mockReset();
  fetchUsuarioResumen.mockReset();
});

describe("POST /api/checkout · pausa", () => {
  // El handler no recibe ni lee el request: suscripción embebida, hospedada
  // y top-up terminan igual.
  it("cualquier compra → 503 dona_en_pausa sin llamar a Stripe", async () => {
    const res = await POST();
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ error: "dona_en_pausa" });
    expect(getStripe).not.toHaveBeenCalled();
    expect(sessionsCreate).not.toHaveBeenCalled();
    expect(auth).not.toHaveBeenCalled();
    expect(fetchUsuarioResumen).not.toHaveBeenCalled();
  });

  it("no queda código de cobro en la ruta (ni price_data inline)", () => {
    const fuente = readFileSync(join(process.cwd(), "app/api/checkout/route.ts"), "utf-8");
    expect(fuente).not.toContain("@/lib/stripe");
    expect(fuente).not.toContain("sessions.create");
    expect(fuente).not.toMatch(/price_data\s*:/);
  });
});
