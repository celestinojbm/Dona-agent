// landing/lib/auth-authorize-cross-customer.test.ts — Issue #345 a nivel de
// `authorize` (auth.ts), no solo del matcher.
//
// auth-matcher.test.ts prueba el matcher aislado. Este archivo ejecuta el
// `authorize` real de NextAuth con el matcher y la derivación de password
// REALES, simulando la pausa desactivada (como quedará al relanzar) y Stripe
// con stubs. Cubre lo que el test del matcher no ve:
//   - la sesión que sale de authorize (stripeCustomerId / subscriptionId /
//     plan) es la del customer cuyo password coincidió, nunca la de otro
//     customer del mismo email;
//   - el ataque fallido cuenta para el lockout (recordLoginAttempt false);
//   - el log de "recovery cross-customer" no se emite;
//   - ningún camino de auth.ts consulta la sub del customer de la víctima.

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type Stripe from "stripe";

type Authorize = (c: Record<string, unknown>) => Promise<unknown>;
let authorize: Authorize | undefined;

vi.mock("next-auth", () => ({
  default: (config: { providers: { authorize: Authorize }[] }) => {
    authorize = config.providers[0].authorize;
    return { handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() };
  },
}));
vi.mock("next-auth/providers/credentials", () => ({
  default: (opts: unknown) => opts,
}));

// Pausa desactivada solo en este test: así se ejerce el camino que quedará
// vivo al relanzar. lib/pausa.ts sigue en true.
vi.mock("@/lib/pausa", () => ({ DONA_EN_PAUSA: false }));

const checkLoginLockout = vi.fn();
const recordLoginAttempt = vi.fn();
vi.mock("@/lib/auth-lockout-bridge", () => ({ checkLoginLockout, recordLoginAttempt }));

// Stub de Stripe: customers por email y subs por customer, con registro de
// qué subs se consultaron.
const customersByEmail: Record<string, Stripe.Customer[]> = {};
const subsByCustomer: Record<string, Stripe.Subscription[]> = {};
const subsConsultadas: string[] = [];
const getStripe = vi.fn(() => ({
  customers: {
    list: async ({ email }: { email: string }) => ({
      data: customersByEmail[email] ?? [],
    }),
  },
  subscriptions: {
    list: async ({ customer }: { customer: string }) => {
      subsConsultadas.push(customer);
      return { data: subsByCustomer[customer] ?? [] };
    },
  },
}));
vi.mock("@/lib/stripe", () => ({ getStripe }));

// Secret de prueba generado en ejecución: no es un secreto real.
const SECRET = crypto.randomBytes(32).toString("hex");
let secretPrevio: string | undefined;

function derivar(customerId: string): string {
  const hex = crypto.createHmac("sha256", SECRET).update(customerId, "utf8").digest("hex");
  return "dona-" + hex.slice(0, 12);
}

function customer(id: string, email: string): Stripe.Customer {
  return { id, object: "customer", email, name: null } as Stripe.Customer;
}

function sub(id: string, customerId: string, status: Stripe.Subscription.Status): Stripe.Subscription {
  return {
    id,
    object: "subscription",
    customer: customerId,
    status,
    items: { object: "list", data: [{ id: `si_${id}`, price: { id: `price_${id}` } }] },
  } as unknown as Stripe.Subscription;
}

const EMAIL = "victima@example.com";

beforeAll(async () => {
  secretPrevio = process.env.DASHBOARD_PASSWORD_SECRET;
  process.env.DASHBOARD_PASSWORD_SECRET = SECRET;
  await import("@/auth");
});

afterAll(() => {
  if (secretPrevio === undefined) delete process.env.DASHBOARD_PASSWORD_SECRET;
  else process.env.DASHBOARD_PASSWORD_SECRET = secretPrevio;
});

beforeEach(() => {
  vi.clearAllMocks();
  subsConsultadas.length = 0;
  for (const k of Object.keys(customersByEmail)) delete customersByEmail[k];
  for (const k of Object.keys(subsByCustomer)) delete subsByCustomer[k];
  checkLoginLockout.mockResolvedValue({ bloqueado: false });
  recordLoginAttempt.mockResolvedValue(undefined);
});

describe("auth.ts · authorize sin recovery cross-customer (issue #345)", () => {
  it.each(["atacante-primero", "victima-primero"] as const)(
    "atacante con customer propio sin sub válida y el email de la víctima → null (%s)",
    async (orden) => {
      const atk = customer("cus_ATK", EMAIL);
      const vic = customer("cus_VIC", EMAIL);
      customersByEmail[EMAIL] = orden === "atacante-primero" ? [atk, vic] : [vic, atk];
      subsByCustomer.cus_ATK = [sub("sub_ATK", "cus_ATK", "canceled")];
      subsByCustomer.cus_VIC = [sub("sub_VIC", "cus_VIC", "active")];
      const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

      const res = await authorize!({ email: EMAIL, password: derivar("cus_ATK") });

      expect(res).toBeNull();
      expect(subsConsultadas).not.toContain("cus_VIC");
      // El intento fallido cuenta para el lockout del email.
      expect(recordLoginAttempt).toHaveBeenCalledTimes(1);
      expect(recordLoginAttempt).toHaveBeenCalledWith(EMAIL, false);
      expect(warn.mock.calls.flat().join(" ")).not.toContain("recovery cross-customer");
      warn.mockRestore();
    },
  );

  it("la víctima con su propio password recibe SU sesión aunque exista el customer atacante", async () => {
    customersByEmail[EMAIL] = [customer("cus_ATK", EMAIL), customer("cus_VIC", EMAIL)];
    subsByCustomer.cus_ATK = [];
    subsByCustomer.cus_VIC = [sub("sub_VIC", "cus_VIC", "active")];

    const res = await authorize!({ email: EMAIL, password: derivar("cus_VIC") });

    expect(res).toMatchObject({
      id: "cus_VIC",
      stripeCustomerId: "cus_VIC",
      subscriptionId: "sub_VIC",
      plan: "price_sub_VIC",
    });
    expect(recordLoginAttempt).toHaveBeenCalledWith(EMAIL, true);
  });

  it("un login correcto no emite avisos y auth.ts no ramifica sobre `recovery`", async () => {
    customersByEmail[EMAIL] = [customer("cus_VIC", EMAIL)];
    subsByCustomer.cus_VIC = [sub("sub_VIC", "cus_VIC", "active")];
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(await authorize!({ email: EMAIL, password: derivar("cus_VIC") })).toMatchObject({
      stripeCustomerId: "cus_VIC",
    });
    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();

    // El matcher ya no tiene recovery (siempre `recovery: false`): una rama o
    // un comentario en auth.ts que hable de él sería código muerto o falso.
    const fuente = fs.readFileSync(path.join(__dirname, "..", "auth.ts"), "utf8");
    expect(fuente).not.toMatch(/match\.recovery|passwordOwnerCustomerId/);
    expect(fuente).not.toMatch(/también autoriza/);
  });

  it("caso legítimo del incidente original (password viejo de cus_OLD, sub en cus_NEW) falla cerrado", async () => {
    customersByEmail[EMAIL] = [customer("cus_OLD", EMAIL), customer("cus_NEW", EMAIL)];
    subsByCustomer.cus_OLD = [];
    subsByCustomer.cus_NEW = [sub("sub_NEW", "cus_NEW", "trialing")];

    expect(await authorize!({ email: EMAIL, password: derivar("cus_OLD") })).toBeNull();
    expect(subsConsultadas).toEqual(["cus_OLD"]);
    expect(recordLoginAttempt).toHaveBeenCalledWith(EMAIL, false);

    // La recuperación (password de cus_NEW entregado por el operador) sí entra.
    expect(await authorize!({ email: EMAIL, password: derivar("cus_NEW") })).toMatchObject({
      stripeCustomerId: "cus_NEW",
      subscriptionId: "sub_NEW",
    });
  });
});
