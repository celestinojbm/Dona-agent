// landing/lib/auth-matcher.test.ts
// Tests del matcher · cubre los escenarios del incidente de login.
// Stripe SDK no se importa: las dependencias se mockean con stubs.

import { describe, it, expect } from "vitest";
import {
  encontrarCustomerConSub,
  ESTADOS_SUB_VALIDOS,
  type AuthMatcherDeps,
} from "./auth-matcher";
import type Stripe from "stripe";

// ─── Helpers de fixtures ─────────────────────────────────────────────

function makeCustomer(
  id: string,
  email: string,
  extra: Partial<Stripe.Customer> = {},
): Stripe.Customer {
  return {
    id,
    object: "customer",
    email,
    name: extra.name ?? null,
    deleted: undefined,
    created: 0,
    livemode: false,
    metadata: {},
    balance: 0,
    currency: null,
    default_source: null,
    delinquent: false,
    description: null,
    discount: null,
    invoice_prefix: null,
    invoice_settings: {
      custom_fields: null,
      default_payment_method: null,
      footer: null,
      rendering_options: null,
    },
    next_invoice_sequence: 1,
    phone: null,
    preferred_locales: [],
    shipping: null,
    tax_exempt: "none",
    test_clock: null,
    ...extra,
  } as Stripe.Customer;
}

function makeDeletedCustomer(id: string): Stripe.DeletedCustomer {
  return {
    id,
    object: "customer",
    deleted: true,
  };
}

function makeSub(
  id: string,
  customerId: string,
  status: Stripe.Subscription.Status,
): Stripe.Subscription {
  return {
    id,
    object: "subscription",
    customer: customerId,
    status,
    items: {
      object: "list",
      data: [
        {
          id: `si_${id}`,
          price: { id: "price_test" },
        } as Stripe.SubscriptionItem,
      ],
      has_more: false,
      url: "",
    },
  } as unknown as Stripe.Subscription;
}

interface StripeStub {
  customersByEmail: Record<string, Array<Stripe.Customer | Stripe.DeletedCustomer>>;
  subsByCustomer: Record<string, Stripe.Subscription[]>;
}

function makeDeps(
  stub: StripeStub,
  passwordTable: Record<string, string>,
  secretAvailable = true,
): AuthMatcherDeps {
  return {
    customers: {
      list: async ({ email }) => ({
        data: stub.customersByEmail[email] ?? [],
      }),
    },
    subscriptions: {
      list: async ({ customer }) => ({
        data: stub.subsByCustomer[customer] ?? [],
      }),
    },
    derivePassword: (cid: string) => {
      if (!secretAvailable) return null;
      return passwordTable[cid] ?? `dona-${cid.slice(-12)}`;
    },
    passwordMatch: (a, b) => a === b,
  };
}

// ─── Tests ──────────────────────────────────────────────────────────

describe("encontrarCustomerConSub", () => {
  it("retorna null si email no tiene customers", async () => {
    const deps = makeDeps(
      { customersByEmail: {}, subsByCustomer: {} },
      {},
    );
    const r = await encontrarCustomerConSub("nadie@x.com", "dona-xxx", deps);
    expect(r).toBeNull();
  });

  it("retorna null si el único customer tiene sub canceled", async () => {
    const c = makeCustomer("cus_A", "ana@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "ana@x.com": [c] },
        subsByCustomer: { cus_A: [makeSub("sub_A", "cus_A", "canceled")] },
      },
      { cus_A: "dona-passA1234" },
    );
    const r = await encontrarCustomerConSub(
      "ana@x.com",
      "dona-passA1234",
      deps,
    );
    expect(r).toBeNull();
  });

  it("ENCUENTRA sub activa cuando hay 2 customers y la sub está en el segundo (caso real del incidente)", async () => {
    const cViejo = makeCustomer("cus_OLD", "celes@x.com");
    const cNuevo = makeCustomer("cus_NEW", "celes@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "celes@x.com": [cViejo, cNuevo] },
        subsByCustomer: {
          cus_OLD: [], // primer customer sin subs
          cus_NEW: [makeSub("sub_NEW", "cus_NEW", "active")],
        },
      },
      {
        cus_OLD: "dona-old123456",
        cus_NEW: "dona-new123456",
      },
    );
    const r = await encontrarCustomerConSub(
      "celes@x.com",
      "dona-new123456",
      deps,
    );
    expect(r).not.toBeNull();
    expect(r?.customer.id).toBe("cus_NEW");
    expect(r?.subscription.id).toBe("sub_NEW");
    expect(r?.subscription.status).toBe("active");
    expect(r?.recovery).toBe(false);
    expect(r?.passwordOwnerCustomerId).toBe("cus_NEW");
  });

  it("RECOVERY · password viejo de cus_OLD + sub activa en cus_NEW autoriza con recovery=true", async () => {
    const cViejo = makeCustomer("cus_OLD", "celes@x.com");
    const cNuevo = makeCustomer("cus_NEW", "celes@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "celes@x.com": [cViejo, cNuevo] },
        subsByCustomer: {
          cus_OLD: [makeSub("sub_OLD", "cus_OLD", "canceled")],
          cus_NEW: [makeSub("sub_NEW", "cus_NEW", "active")],
        },
      },
      {
        cus_OLD: "dona-oldpass1234",
        cus_NEW: "dona-newpass5678",
      },
    );
    // El usuario solo conoce el password de cus_OLD (su welcome viejo).
    const r = await encontrarCustomerConSub(
      "celes@x.com",
      "dona-oldpass1234",
      deps,
    );
    expect(r).not.toBeNull();
    expect(r?.customer.id).toBe("cus_NEW"); // dashboard del customer con sub
    expect(r?.subscription.id).toBe("sub_NEW");
    expect(r?.recovery).toBe(true);
    expect(r?.passwordOwnerCustomerId).toBe("cus_OLD");
  });

  it("RECOVERY · si NINGÚN password de los customers del email coincide, no autoriza ni siquiera con sub activa presente (sin ownership)", async () => {
    const cViejo = makeCustomer("cus_OLD", "x@x.com");
    const cNuevo = makeCustomer("cus_NEW", "x@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "x@x.com": [cViejo, cNuevo] },
        subsByCustomer: {
          cus_OLD: [],
          cus_NEW: [makeSub("sub_NEW", "cus_NEW", "active")],
        },
      },
      {
        cus_OLD: "dona-realold1234",
        cus_NEW: "dona-realnew5678",
      },
    );
    // password no coincide con ninguno · sin ownership demostrado
    const r = await encontrarCustomerConSub(
      "x@x.com",
      "dona-attacker0000",
      deps,
    );
    expect(r).toBeNull();
  });

  it("RECOVERY · ownership demostrado pero NINGÚN customer del email tiene sub válida → null", async () => {
    const cViejo = makeCustomer("cus_OLD", "x@x.com");
    const cNuevo = makeCustomer("cus_NEW", "x@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "x@x.com": [cViejo, cNuevo] },
        subsByCustomer: {
          cus_OLD: [makeSub("sub_OLD", "cus_OLD", "canceled")],
          cus_NEW: [makeSub("sub_NEW", "cus_NEW", "incomplete")],
        },
      },
      {
        cus_OLD: "dona-oldpass1234",
        cus_NEW: "dona-newpass5678",
      },
    );
    const r = await encontrarCustomerConSub(
      "x@x.com",
      "dona-oldpass1234",
      deps,
    );
    expect(r).toBeNull();
  });

  it("password incorrecto del primer customer no impide encontrar el segundo con password correcto", async () => {
    const c1 = makeCustomer("cus_1", "x@x.com");
    const c2 = makeCustomer("cus_2", "x@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "x@x.com": [c1, c2] },
        subsByCustomer: {
          cus_1: [makeSub("sub_1", "cus_1", "active")],
          cus_2: [makeSub("sub_2", "cus_2", "active")],
        },
      },
      {
        cus_1: "dona-aaaa11112222",
        cus_2: "dona-bbbb33334444",
      },
    );
    // password coincide solo con cus_2
    const r = await encontrarCustomerConSub("x@x.com", "dona-bbbb33334444", deps);
    expect(r?.customer.id).toBe("cus_2");
  });

  it("acepta sub en estado trialing", async () => {
    const c = makeCustomer("cus_T", "t@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "t@x.com": [c] },
        subsByCustomer: { cus_T: [makeSub("sub_T", "cus_T", "trialing")] },
      },
      { cus_T: "dona-trialPass1" },
    );
    const r = await encontrarCustomerConSub("t@x.com", "dona-trialPass1", deps);
    expect(r?.subscription.status).toBe("trialing");
  });

  it("acepta sub en estado past_due (UX permite que el usuario llegue al portal a actualizar tarjeta)", async () => {
    const c = makeCustomer("cus_P", "p@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "p@x.com": [c] },
        subsByCustomer: { cus_P: [makeSub("sub_P", "cus_P", "past_due")] },
      },
      { cus_P: "dona-pastDue1234" },
    );
    const r = await encontrarCustomerConSub("p@x.com", "dona-pastDue1234", deps);
    expect(r?.subscription.status).toBe("past_due");
  });

  it("rechaza sub en estado incomplete", async () => {
    const c = makeCustomer("cus_I", "i@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "i@x.com": [c] },
        subsByCustomer: { cus_I: [makeSub("sub_I", "cus_I", "incomplete")] },
      },
      { cus_I: "dona-incompletex" },
    );
    const r = await encontrarCustomerConSub("i@x.com", "dona-incompletex", deps);
    expect(r).toBeNull();
  });

  it("salta customers con deleted=true", async () => {
    const cDeleted = makeDeletedCustomer("cus_DEL");
    const cActivo = makeCustomer("cus_OK", "d@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "d@x.com": [cDeleted, cActivo] },
        subsByCustomer: { cus_OK: [makeSub("sub_OK", "cus_OK", "active")] },
      },
      { cus_OK: "dona-okPass1234" },
    );
    const r = await encontrarCustomerConSub("d@x.com", "dona-okPass1234", deps);
    expect(r?.customer.id).toBe("cus_OK");
  });

  it("retorna null si DASHBOARD_PASSWORD_SECRET no está configurada (derivePassword devuelve null)", async () => {
    const c = makeCustomer("cus_X", "x@x.com");
    const deps = makeDeps(
      {
        customersByEmail: { "x@x.com": [c] },
        subsByCustomer: { cus_X: [makeSub("sub_X", "cus_X", "active")] },
      },
      {},
      false, // secret NO disponible
    );
    const r = await encontrarCustomerConSub("x@x.com", "dona-anything", deps);
    expect(r).toBeNull();
  });

  it("retorna null si email vacío", async () => {
    const deps = makeDeps({ customersByEmail: {}, subsByCustomer: {} }, {});
    expect(await encontrarCustomerConSub("", "dona-x", deps)).toBeNull();
  });

  it("retorna null si password vacío", async () => {
    const deps = makeDeps({ customersByEmail: {}, subsByCustomer: {} }, {});
    expect(await encontrarCustomerConSub("a@x.com", "", deps)).toBeNull();
  });

  it("ESTADOS_SUB_VALIDOS contiene exactamente active, trialing, past_due", () => {
    expect([...ESTADOS_SUB_VALIDOS].sort()).toEqual(
      ["active", "past_due", "trialing"],
    );
  });
});
