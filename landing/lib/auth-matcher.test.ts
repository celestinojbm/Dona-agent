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
  /** Si se pasa, registra cada customer_id cuya sub se consultó. */
  llamadasSubs?: string[],
): AuthMatcherDeps {
  return {
    customers: {
      list: async ({ email }) => ({
        data: stub.customersByEmail[email] ?? [],
      }),
    },
    subscriptions: {
      list: async ({ customer }) => {
        llamadasSubs?.push(customer);
        return { data: stub.subsByCustomer[customer] ?? [] };
      },
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

  it("SIN RECOVERY · password viejo de cus_OLD + sub activa en cus_NEW → null (fail-closed, issue #345)", async () => {
    const cViejo = makeCustomer("cus_OLD", "celes@x.com");
    const cNuevo = makeCustomer("cus_NEW", "celes@x.com");
    const llamadasSubs: string[] = [];
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
      true,
      llamadasSubs,
    );
    // El usuario solo conoce el password de cus_OLD (su welcome viejo).
    // Ya no basta: conocer el password de un customer sin sub no prueba
    // titularidad del email. La recuperación va por fuera del login
    // (scripts/derive-dashboard-password.ts para cus_NEW).
    const r = await encontrarCustomerConSub(
      "celes@x.com",
      "dona-oldpass1234",
      deps,
    );
    expect(r).toBeNull();
    // Ni siquiera se consulta la sub de cus_NEW.
    expect(llamadasSubs).toEqual(["cus_OLD"]);

    // El mismo usuario con el password de cus_NEW sí entra.
    const ok = await encontrarCustomerConSub(
      "celes@x.com",
      "dona-newpass5678",
      deps,
    );
    expect(ok?.customer.id).toBe("cus_NEW");
    expect(ok?.subscription.id).toBe("sub_NEW");
    expect(ok?.recovery).toBe(false);
    expect(ok?.passwordOwnerCustomerId).toBe("cus_NEW");
  });

  it("si NINGÚN password de los customers del email coincide, no autoriza aunque haya sub activa", async () => {
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
    // password no coincide con ninguno
    const r = await encontrarCustomerConSub(
      "x@x.com",
      "dona-attacker0000",
      deps,
    );
    expect(r).toBeNull();
  });

  it("password coincide con un customer pero NINGÚN customer del email tiene sub válida → null", async () => {
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

  // ─── Ataque del issue #345: customer atacante sin sub + email de la víctima ───

  describe("ATAQUE · customer propio sin sub válida con el email de la víctima", () => {
    const EMAIL_VICTIMA = "victima@x.com";
    const PWD_ATACANTE = "dona-atk000000000";
    const PWD_VICTIMA = "dona-vic111111111";

    function escenario(
      subsAtacante: Stripe.Subscription[],
      orden: "atacante-primero" | "victima-primero" = "atacante-primero",
      llamadasSubs?: string[],
    ) {
      const cAtk = makeCustomer("cus_ATK", EMAIL_VICTIMA);
      const cVic = makeCustomer("cus_VIC", EMAIL_VICTIMA);
      const lista = orden === "atacante-primero" ? [cAtk, cVic] : [cVic, cAtk];
      return makeDeps(
        {
          customersByEmail: { [EMAIL_VICTIMA]: lista },
          subsByCustomer: {
            cus_ATK: subsAtacante,
            cus_VIC: [makeSub("sub_VIC", "cus_VIC", "active")],
          },
        },
        { cus_ATK: PWD_ATACANTE, cus_VIC: PWD_VICTIMA },
        true,
        llamadasSubs,
      );
    }

    it("atacante sin ninguna sub + su propio password → null, no devuelve la sesión de la víctima", async () => {
      const llamadasSubs: string[] = [];
      const r = await encontrarCustomerConSub(
        EMAIL_VICTIMA,
        PWD_ATACANTE,
        escenario([], "atacante-primero", llamadasSubs),
      );
      expect(r).toBeNull();
      // Fail-closed estructural: nunca se consulta la sub de un customer
      // cuyo password no coincidió.
      expect(llamadasSubs).not.toContain("cus_VIC");
    });

    it("mismo ataque con la víctima listada primero → null", async () => {
      const llamadasSubs: string[] = [];
      const r = await encontrarCustomerConSub(
        EMAIL_VICTIMA,
        PWD_ATACANTE,
        escenario([], "victima-primero", llamadasSubs),
      );
      expect(r).toBeNull();
      expect(llamadasSubs).not.toContain("cus_VIC");
    });

    it.each(["canceled", "incomplete", "incomplete_expired", "unpaid", "paused"] as const)(
      "atacante con sub %s + su propio password → null",
      async (estado) => {
        const r = await encontrarCustomerConSub(
          EMAIL_VICTIMA,
          PWD_ATACANTE,
          escenario([makeSub("sub_ATK", "cus_ATK", estado)]),
        );
        expect(r).toBeNull();
      },
    );

    it("la víctima sigue entrando con su propio password aunque exista el customer atacante", async () => {
      const r = await encontrarCustomerConSub(
        EMAIL_VICTIMA,
        PWD_VICTIMA,
        escenario([]),
      );
      expect(r?.customer.id).toBe("cus_VIC");
      expect(r?.subscription.id).toBe("sub_VIC");
      expect(r?.recovery).toBe(false);
      expect(r?.passwordOwnerCustomerId).toBe("cus_VIC");
    });

    it("con varios customers del email, la sesión devuelta es siempre la del customer cuyo password coincidió", async () => {
      const c1 = makeCustomer("cus_1", "m@x.com");
      const c2 = makeCustomer("cus_2", "m@x.com");
      const c3 = makeCustomer("cus_3", "m@x.com");
      const deps = makeDeps(
        {
          customersByEmail: { "m@x.com": [c1, c2, c3] },
          subsByCustomer: {
            cus_1: [makeSub("sub_1", "cus_1", "active")],
            cus_2: [],
            cus_3: [makeSub("sub_3", "cus_3", "trialing")],
          },
        },
        {
          cus_1: "dona-111111111111",
          cus_2: "dona-222222222222",
          cus_3: "dona-333333333333",
        },
      );
      expect(
        await encontrarCustomerConSub("m@x.com", "dona-222222222222", deps),
      ).toBeNull();
      const r3 = await encontrarCustomerConSub(
        "m@x.com",
        "dona-333333333333",
        deps,
      );
      expect(r3?.customer.id).toBe("cus_3");
      expect(r3?.subscription.id).toBe("sub_3");
      expect(r3?.passwordOwnerCustomerId).toBe("cus_3");
    });
  });

  it("ESTADOS_SUB_VALIDOS contiene exactamente active, trialing, past_due", () => {
    expect([...ESTADOS_SUB_VALIDOS].sort()).toEqual(
      ["active", "past_due", "trialing"],
    );
  });
});
