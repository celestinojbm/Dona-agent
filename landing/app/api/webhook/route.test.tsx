// landing/app/api/webhook/route.test.tsx — Webhook de Stripe en pausa.
//
// Firma real generada con el helper de stripe-node (sin red ni API key).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Stripe from "stripe";
import type { NextRequest } from "next/server";

const getStripeSpy = vi.fn();
vi.mock("@/lib/stripe", () => ({ getStripe: getStripeSpy }));

import { POST } from "./route";

const SECRET = "whsec_test_pausa_fixture";

// Payload con datos personales FICTICIOS: no deben aparecer en los logs.
const payload = JSON.stringify({
  id: "evt_test_pausa_1",
  object: "event",
  type: "checkout.session.completed",
  created: 1_760_000_000,
  livemode: false,
  data: {
    object: {
      id: "cs_test_x",
      customer_email: "persona@example.com",
      metadata: { phone: "+15550000000", plan: "premium" },
      amount_total: 2000,
    },
  },
});

function req(body: string, headers: Record<string, string> = {}): NextRequest {
  return new Request("http://test/api/webhook", {
    method: "POST",
    headers,
    body,
  }) as unknown as NextRequest;
}

function firmado(body: string, secret = SECRET): NextRequest {
  const header = Stripe.webhooks.generateTestHeaderString({ payload: body, secret });
  return req(body, { "stripe-signature": header });
}

const fetchSpy = vi.fn();
let logs: string[];

beforeEach(() => {
  vi.stubEnv("STRIPE_WEBHOOK_SECRET", SECRET);
  vi.stubEnv("STRIPE_SECRET_KEY", "");
  fetchSpy.mockReset();
  getStripeSpy.mockReset();
  vi.stubGlobal("fetch", fetchSpy);
  logs = [];
  for (const nivel of ["log", "warn", "error", "info"] as const) {
    vi.spyOn(console, nivel).mockImplementation((...args: unknown[]) => {
      logs.push(args.map(String).join(" "));
    });
  }
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("POST /api/webhook (Stripe) · pausa", () => {
  it("evento con firma válida → 200 paused, sin bridge ni Stripe API", async () => {
    const res = await POST(firmado(payload));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ received: true, paused: true });
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(getStripeSpy).not.toHaveBeenCalled();
  });

  it("registra solo evidencia mínima: id, tipo, livemode y created", async () => {
    await POST(firmado(payload));
    const todo = logs.join("\n");
    expect(todo).toContain("evt_test_pausa_1");
    expect(todo).toContain("checkout.session.completed");
    expect(todo).not.toContain("persona@example.com");
    expect(todo).not.toContain("+15550000000");
    expect(todo).not.toContain("2000");
    expect(todo).not.toContain("cs_test_x");
  });

  it("firma inválida → 400", async () => {
    const res = await POST(firmado(payload, "whsec_otro_secreto"));
    expect(res.status).toBe(400);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("cuerpo alterado tras firmar → 400", async () => {
    const header = Stripe.webhooks.generateTestHeaderString({ payload, secret: SECRET });
    const res = await POST(req(payload.replace("premium", "pro"), { "stripe-signature": header }));
    expect(res.status).toBe(400);
  });

  it("sin cabecera de firma → 400", async () => {
    const res = await POST(req(payload));
    expect(res.status).toBe(400);
  });

  it("sin STRIPE_WEBHOOK_SECRET → 503 y no acepta el evento sin validar", async () => {
    vi.stubEnv("STRIPE_WEBHOOK_SECRET", "");
    const res = await POST(firmado(payload));
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: "webhook_no_configurado" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
