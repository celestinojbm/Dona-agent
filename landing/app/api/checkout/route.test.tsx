// landing/app/api/checkout/route.test.tsx — checkout embebido vs hospedado
//
// El route crea la sesión de Stripe 100% server-side. Estos tests fijan el
// contrato del modo embedded (ui_mode + return_url + clientSecret) y que el
// modo hospedado (default) no cambió. Stripe y auth van mockeados.

import { describe, it, expect, vi, beforeEach } from "vitest";

const sessionsCreate = vi.fn();

vi.mock("@/lib/stripe", () => ({
  getStripe: () => ({ checkout: { sessions: { create: sessionsCreate } } }),
  PLANS: {
    premium: { name: "Premium", price: 2000, priceId: undefined },
    pro: { name: "Pro", price: 4000, priceId: "price_pro_test" },
  },
  PAQUETES: {},
}));
vi.mock("@/auth", () => ({ auth: vi.fn() }));
vi.mock("@/lib/internal-bridge", () => ({ fetchUsuarioResumen: vi.fn() }));

import type { NextRequest } from "next/server";
import { POST } from "./route";

function reqCon(body: unknown): NextRequest {
  // El handler solo usa .json() y .headers.get("origin"); un Request normal
  // basta en runtime — el cast es solo para el tipo NextRequest.
  return new Request("http://test/api/checkout", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      origin: "http://test",
    },
    body: JSON.stringify(body),
  }) as unknown as NextRequest;
}

beforeEach(() => {
  sessionsCreate.mockReset();
});

describe("POST /api/checkout · suscripción embebida", () => {
  it("embedded:true crea sesión ui_mode=embedded_page con return_url y devuelve clientSecret", async () => {
    sessionsCreate.mockResolvedValueOnce({
      client_secret: "cs_test_secret_123",
    });
    const res = await POST(reqCon({ plan: "pro", embedded: true }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ clientSecret: "cs_test_secret_123" });

    const args = sessionsCreate.mock.calls[0][0];
    // "embedded_page" es el UiMode del Embedded Checkout en stripe v22.
    expect(args.ui_mode).toBe("embedded_page");
    expect(args.return_url).toBe(
      "http://test/success?session_id={CHECKOUT_SESSION_ID}",
    );
    // Embedded NO lleva success/cancel_url (Stripe los rechaza con ui_mode).
    expect(args.success_url).toBeUndefined();
    expect(args.cancel_url).toBeUndefined();
    // El teléfono se sigue pidiendo: es lo que vincula la cuenta a WhatsApp.
    expect(args.phone_number_collection).toEqual({ enabled: true });
    expect(args.mode).toBe("subscription");
    expect(args.metadata).toMatchObject({ kind: "subscription", plan: "pro" });
  });

  it("embedded sin client_secret en la sesión → 502 (no devuelve url rota)", async () => {
    sessionsCreate.mockResolvedValueOnce({ client_secret: null });
    const res = await POST(reqCon({ plan: "premium", embedded: true }));
    expect(res.status).toBe(502);
  });

  it("embedded con plan inválido → 400 sin llamar a Stripe", async () => {
    const res = await POST(reqCon({ plan: "hacker", embedded: true }));
    expect(res.status).toBe(400);
    expect(sessionsCreate).not.toHaveBeenCalled();
  });

  it("embedded como string ('true') NO activa el modo embebido (boolean estricto)", async () => {
    sessionsCreate.mockResolvedValueOnce({ url: "https://stripe.test/s" });
    const res = await POST(reqCon({ plan: "pro", embedded: "true" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ url: "https://stripe.test/s" });
    expect(sessionsCreate.mock.calls[0][0].ui_mode).toBeUndefined();
  });
});

describe("POST /api/checkout · hospedado (compat, default)", () => {
  it("sin embedded devuelve url con success/cancel_url como siempre", async () => {
    sessionsCreate.mockResolvedValueOnce({ url: "https://stripe.test/sesion" });
    const res = await POST(reqCon({ plan: "premium" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ url: "https://stripe.test/sesion" });

    const args = sessionsCreate.mock.calls[0][0];
    expect(args.ui_mode).toBeUndefined();
    expect(args.success_url).toBe(
      "http://test/success?session_id={CHECKOUT_SESSION_ID}",
    );
    expect(args.cancel_url).toBe("http://test/cancel");
    expect(args.phone_number_collection).toEqual({ enabled: true });
  });

  it("usa priceId cuando está configurado y price_data inline cuando no", async () => {
    sessionsCreate.mockResolvedValue({ url: "https://stripe.test/s" });
    await POST(reqCon({ plan: "pro" }));
    expect(sessionsCreate.mock.calls[0][0].line_items).toEqual([
      { price: "price_pro_test", quantity: 1 },
    ]);
    await POST(reqCon({ plan: "premium" }));
    const li = sessionsCreate.mock.calls[1][0].line_items[0];
    expect(li.price_data.unit_amount).toBe(2000);
    expect(li.price_data.recurring).toEqual({ interval: "month" });
  });
});
