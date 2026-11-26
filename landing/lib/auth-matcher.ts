// landing/lib/auth-matcher.ts
//
// Matcher del login del dashboard. Histórico:
//
// v1 (pre-hotfix): customers.list({ email, limit: 1 }) + status: 'active'.
//   Bug A: solo miraba el primer customer; con duplicados fallaba.
//   Bug B: rechazaba trialing y past_due.
//
// v2 (hotfix anterior): itera limit:100 customers, valida password contra
//   cada uno, acepta active/trialing/past_due.
//   Gap residual: si el password coincide con cus_OLD (sin sub válida) y
//   la sub está en cus_NEW (cuyo password derivado es DISTINTO porque la
//   derivación usa customer_id), el matcher rechaza el login. Caso real
//   reportado en producción.
//
// v3: dos pasadas. Pass 1 = match exacto (password ↔ customer con sub
//   válida). Pass 2 = "recovery cross-customer": si el password coincidía
//   con un customer SIN sub válida, autorizaba contra OTRO customer del
//   mismo email que sí la tuviera.
//
// v4 (este archivo): se elimina el Pass 2 (issue #345). Queda solo el
//   match exacto: el password tiene que ser el derivado del MISMO customer
//   cuya sub autoriza la sesión.
//
// Por qué el Pass 2 era inseguro:
//   - El supuesto de v3 era "si el password derivado de un customer_id
//     coincide, el usuario demostró posesión del email". Falso: Stripe
//     permite varios customers con el mismo email y no verifica que quien
//     crea un customer controle ese buzón.
//   - Ataque: alguien crea (o ya tiene) un customer propio sin sub válida
//     con el email de la víctima y conoce el password derivado de ESE
//     customer. Pass 1 falla; Pass 2 le entregaba la sesión del customer
//     de la víctima (id, stripeCustomerId, subscriptionId, plan).
//   - Conocer el password de un customer prueba, como mucho, que alguien
//     te lo entregó para ESE customer_id. No prueba titularidad del correo
//     ni autoriza la sesión de otro customer.
//
// Caso legítimo que v3 cubría (password viejo de cus_OLD, sub en cus_NEW):
//   ahora el login falla cerrado. La recuperación se hace fuera de este
//   path: el operador verifica al usuario por su canal (WhatsApp) y le
//   entrega el password de cus_NEW regenerándolo con
//   scripts/derive-dashboard-password.ts. Si algún día se reintroduce un
//   recovery automático, tiene que exigir prueba de control del buzón
//   (correo verificado / magic link), nunca solo "sé el password de un
//   customer de este email".

import type Stripe from "stripe";

export const ESTADOS_SUB_VALIDOS = [
  "active",
  "trialing",
  "past_due",
] as const;

export type EstadoSubValido = (typeof ESTADOS_SUB_VALIDOS)[number];

export interface AuthMatch {
  /**
   * Customer cuyo dashboard se autoriza. Siempre es el mismo customer cuyo
   * password derivado coincidió y el que tiene la sub válida.
   */
  customer: Stripe.Customer;
  /** Subscription en estado válido (active/trialing/past_due) de `customer`. */
  subscription: Stripe.Subscription;
  /**
   * Siempre false desde v4 (sin recovery cross-customer). Tipado como
   * literal para que reintroducir un recovery obligue a cambiar el contrato
   * a propósito. auth.ts no lo lee; los tests lo usan como invariante.
   */
  recovery: false;
  /** Customer cuyo password validó · desde v4 siempre igual a `customer.id`. */
  passwordOwnerCustomerId: string;
}

export interface AuthMatcherDeps {
  customers: {
    list: (params: {
      email: string;
      limit?: number;
    }) => Promise<{ data: Array<Stripe.Customer | Stripe.DeletedCustomer> }>;
  };
  subscriptions: {
    list: (params: {
      customer: string;
      status?: Stripe.SubscriptionListParams.Status;
      limit?: number;
    }) => Promise<{ data: Stripe.Subscription[] }>;
  };
  derivePassword: (customerId: string) => string | null;
  passwordMatch: (a: string, b: string) => boolean;
}

function esCustomerActivo(
  c: Stripe.Customer | Stripe.DeletedCustomer,
): c is Stripe.Customer {
  return c.object === "customer" && !("deleted" in c && c.deleted === true);
}

function tieneSubValida(
  subs: Stripe.Subscription[],
): Stripe.Subscription | null {
  return (
    subs.find((s) =>
      (ESTADOS_SUB_VALIDOS as readonly string[]).includes(s.status),
    ) ?? null
  );
}

async function buscarSubValida(
  customerId: string,
  deps: AuthMatcherDeps,
): Promise<Stripe.Subscription | null> {
  const subs = await deps.subscriptions.list({
    customer: customerId,
    status: "all",
    limit: 10,
  });
  return tieneSubValida(subs.data);
}

/**
 * Encuentra el (customer, subscription) que autoriza el login.
 *
 * Solo match exacto: el password tiene que coincidir con el derivado de un
 * customer del email que TENGA sub válida, y la sesión es la de ese mismo
 * customer. Nunca se autoriza contra un customer distinto del que validó
 * el password (ver header).
 *
 * Retorna null si:
 *   - email o password vacíos
 *   - ningún customer con ese email
 *   - password no coincide con ningún customer del email
 *   - el customer cuyo password coincide no tiene sub válida (aunque otro
 *     customer del mismo email sí la tenga)
 */
export async function encontrarCustomerConSub(
  email: string,
  password: string,
  deps: AuthMatcherDeps,
): Promise<AuthMatch | null> {
  if (!email || !password) return null;

  const customers = await deps.customers.list({ email, limit: 100 });

  for (const raw of customers.data) {
    if (!esCustomerActivo(raw)) continue;
    if (raw.email !== email) continue;

    const expected = deps.derivePassword(raw.id);
    if (!expected) continue;
    if (!deps.passwordMatch(password, expected)) continue;

    // Solo se consulta la sub del customer cuyo password coincidió. Si no
    // tiene sub válida, se sigue buscando otro customer cuyo password
    // coincida (en la práctica no hay: la derivación es por customer_id),
    // pero NUNCA se mira la sub de un customer cuyo password no coincidió.
    const sub = await buscarSubValida(raw.id, deps);
    if (sub) {
      return {
        customer: raw,
        subscription: sub,
        recovery: false,
        passwordOwnerCustomerId: raw.id,
      };
    }
  }

  return null;
}
