// landing/app/api/dashboard-data/route.test.tsx — Datos mínimos de preview.
//
// La sesión del dueño no trae subscriptionId. Solo con VERCEL_ENV=preview
// y session.preview la ruta responde un JSON vacío, sin Stripe ni backend.
// En cualquier otro entorno sigue el 403 de producción.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { datosMinimosPreview } from "@/lib/preview-login";

const { auth, getStripe, fetchUsuarioResumen } = vi.hoisted(() => ({
  auth: vi.fn(),
  getStripe: vi.fn(() => {
    throw new Error("Stripe no debe usarse");
  }),
  fetchUsuarioResumen: vi.fn(),
}));

vi.mock("@/auth", () => ({ auth }));
vi.mock("@/lib/stripe", () => ({ getStripe }));
vi.mock("@/lib/internal-bridge", () => ({ fetchUsuarioResumen }));

import { GET } from "./route";

const RESUMEN_REAL = {
  usuario: { id: "u1", email: "cliente@example.com", telefono: "15550001111" },
  creditos: { saldo_actual: 10, creditos_mensuales: 100, ultimo_movimiento: null },
  suscripcion: {
    estado: "active",
    plan: "premium",
    stripe_customer_id: "cus_real",
    stripe_subscription_id: "sub_real",
    current_period_end: null,
    cancel_at_period_end: false,
    actualizado: null,
  },
  transacciones_recientes: [],
  resumen: { puede_cancelar: true, dashboard_ready: true },
};

beforeEach(() => {
  auth.mockReset();
  getStripe.mockClear();
  fetchUsuarioResumen.mockReset();
  vi.stubEnv("STRIPE_SECRET_KEY", "");
  vi.stubEnv("VERCEL_ENV", "");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("GET /api/dashboard-data · preview", () => {
  it("en preview devuelve datos mínimos y no llama a Stripe ni al backend", async () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    auth.mockResolvedValue({
      user: { email: "dueno@example.com" },
      preview: true,
      plan: "preview",
    });

    const res = await GET();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(datosMinimosPreview("dueno@example.com"));
    expect(getStripe).not.toHaveBeenCalled();
    expect(fetchUsuarioResumen).not.toHaveBeenCalled();
  });

  it.each(["production", "development", ""])(
    "VERCEL_ENV=%j con la marca preview responde 403 y no llama a Stripe",
    async (env) => {
      vi.stubEnv("VERCEL_ENV", env);
      auth.mockResolvedValue({
        user: { email: "dueno@example.com" },
        preview: true,
      });

      const res = await GET();
      expect(res.status).toBe(403);
      expect(await res.json()).toEqual({ error: "no_subscription_in_session" });
      expect(getStripe).not.toHaveBeenCalled();
      expect(fetchUsuarioResumen).not.toHaveBeenCalled();
    },
  );

  it("una suscripción real en preview sigue el camino del backend", async () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    auth.mockResolvedValue({
      user: { email: "cliente@example.com" },
      preview: true,
      subscriptionId: "sub_real",
    });
    fetchUsuarioResumen.mockResolvedValue({ ok: true, data: RESUMEN_REAL });

    const res = await GET();
    expect(res.status).toBe(200);
    expect(fetchUsuarioResumen).toHaveBeenCalledWith("sub_real");
    expect(getStripe).not.toHaveBeenCalled();
    const body = await res.json();
    expect(body.suscripcion.stripe_subscription_id).toBe("sub_real");
    expect(body.creditos.saldo_actual).toBe(10);
  });

  it("sin sesión responde 401", async () => {
    vi.stubEnv("VERCEL_ENV", "preview");
    auth.mockResolvedValue(null);
    const res = await GET();
    expect(res.status).toBe(401);
    expect(getStripe).not.toHaveBeenCalled();
    expect(fetchUsuarioResumen).not.toHaveBeenCalled();
  });
});
