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
// v3 (este archivo): dos pasadas.
//   Pass 1 — match exacto: password coincide con un customer que TIENE
//   sub válida. Igual a v2.
//   Pass 2 — recovery cross-customer: si Pass 1 no encontró match pero
//   el password coincidió con AL MENOS un customer del mismo email
//   (ownership demostrado), buscar otro customer del mismo email que
//   tenga sub válida y autorizar contra ése. El return incluye el flag
//   `recovery: true` por si el caller quisiera loguearlo o flaggearlo
//   en métricas; no afecta la sesión.
//
// Por qué Pass 2 es seguro:
//   - El password derivado de un customer_id solo lo conoce quien recibió
//     el welcome de ese customer. Si match, el usuario probó posesión
//     legítima del email.
//   - Stripe tratá los customers con mismo email como "el mismo cliente
//     desde el punto de vista del usuario humano". Que el ownership de
//     uno habilite acceso al dashboard de la sub activa del mismo email
//     es coherente con cómo el usuario percibe su cuenta.
//   - Riesgo residual: si dos humanos distintos por accidente comparten
//     un email, uno con password de su customer puede ver dashboard del
//     otro. Riesgo de baja probabilidad y aceptable; el modelo de Dona
//     asume 1 email = 1 cliente.

import type Stripe from "stripe";

export const ESTADOS_SUB_VALIDOS = [
  "active",
  "trialing",
  "past_due",
] as const;

export type EstadoSubValido = (typeof ESTADOS_SUB_VALIDOS)[number];

export interface AuthMatch {
  /** Customer cuyo dashboard se autoriza · siempre el de la sub válida. */
  customer: Stripe.Customer;
  /** Subscription en estado válido (active/trialing/past_due). */
  subscription: Stripe.Subscription;
  /**
   * true si el password coincidió con OTRO customer del mismo email y la
   * sub está en éste. Implica que el usuario tiene un password "viejo"
   * de un customer duplicado.
   */
  recovery: boolean;
  /**
   * Customer cuyo password validó (puede ser igual a `customer` o no).
   * Útil para que el caller logue el incidente sin filtrar PII.
   */
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
 * Estrategia en dos pasadas — ver header del archivo para razonamiento.
 *
 * Retorna null si:
 *   - email o password vacíos
 *   - ningún customer con ese email
 *   - password no coincide con ningún customer del email (no hay ownership)
 *   - ownership demostrado pero NINGÚN customer del email tiene sub válida
 */
export async function encontrarCustomerConSub(
  email: string,
  password: string,
  deps: AuthMatcherDeps,
): Promise<AuthMatch | null> {
  if (!email || !password) return null;

  const customers = await deps.customers.list({ email, limit: 100 });

  // Filtrar a customers activos y con email exacto. Hacemos esto una
  // vez para no recorrer dos veces.
  const candidatos: Stripe.Customer[] = [];
  for (const raw of customers.data) {
    if (!esCustomerActivo(raw)) continue;
    if (raw.email !== email) continue;
    candidatos.push(raw);
  }

  if (candidatos.length === 0) return null;

  // Pass 1 — match exacto: password ↔ customer con sub válida.
  let passwordOwner: Stripe.Customer | null = null;
  for (const c of candidatos) {
    const expected = deps.derivePassword(c.id);
    if (!expected) continue;
    if (!deps.passwordMatch(password, expected)) continue;

    // Password coincide con este customer · marcamos ownership.
    passwordOwner = c;

    const sub = await buscarSubValida(c.id, deps);
    if (sub) {
      return {
        customer: c,
        subscription: sub,
        recovery: false,
        passwordOwnerCustomerId: c.id,
      };
    }
  }

  // Pass 2 — recovery: ownership demostrado pero el customer dueño del
  // password no tiene sub válida. Buscar entre los OTROS customers del
  // mismo email uno que sí tenga.
  if (!passwordOwner) return null;

  for (const c of candidatos) {
    if (c.id === passwordOwner.id) continue;
    const sub = await buscarSubValida(c.id, deps);
    if (sub) {
      return {
        customer: c,
        subscription: sub,
        recovery: true,
        passwordOwnerCustomerId: passwordOwner.id,
      };
    }
  }

  return null;
}
