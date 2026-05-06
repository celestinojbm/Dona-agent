// landing/lib/auth-matcher.ts
// Hotfix incidente login: usuarios con suscripción activa veían
// "Tu suscripción no está activa" cuando Stripe tenía MÚLTIPLES customers
// con el mismo email y el primero (el más antiguo) no tenía sub válida.
//
// Antes:
//   - auth.ts hacía customers.list({ email, limit: 1 }) → solo veía el
//     primer customer que Stripe devolvía. Si la sub estaba en el segundo
//     o tercer customer, el login fallaba.
//   - subscriptions.list filtraba por status: "active" → trialing y
//     past_due quedaban fuera.
//
// Ahora:
//   - Iterar TODOS los customers con ese email (limit 100, suficiente
//     para cualquier escenario realista).
//   - Para cada candidato verificar password derivado · si match, buscar
//     sub en estado válido (active, trialing, past_due).
//   - Devolver el primer (customer, subscription) que cumpla todo.
//
// Diseño puro y testeable: las dependencias (customers.list,
// subscriptions.list, derivePassword, passwordMatch) se inyectan, no se
// importan. Eso permite tests con stubs sin tocar Stripe.

import type Stripe from "stripe";

/**
 * Estados de suscripción que se consideran "acceso al dashboard".
 *
 * - active   · pago al día.
 * - trialing · trial vigente. Si en el futuro se ofrecen trials, ya
 *              entran sin tocar más código.
 * - past_due · el último pago falló pero Stripe todavía no canceló la
 *              sub (configurable en Stripe). Se admite acceso porque el
 *              dashboard tiene el banner "Pago atrasado" y el botón
 *              "Gestionar facturación" (Customer Portal) que justamente
 *              sirve para que el usuario actualice su tarjeta. Cerrarles
 *              el dashboard sería contraproducente.
 *
 * NO incluidos: incomplete, incomplete_expired, canceled, unpaid, paused.
 */
export const ESTADOS_SUB_VALIDOS = [
  "active",
  "trialing",
  "past_due",
] as const;

export type EstadoSubValido = (typeof ESTADOS_SUB_VALIDOS)[number];

export interface AuthMatch {
  customer: Stripe.Customer;
  subscription: Stripe.Subscription;
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

/**
 * Encuentra el (customer, subscription) que satisface las tres condiciones
 * de login: email coincide · password derivado coincide · sub en estado
 * válido. Si hay múltiples customers con el mismo email, prueba todos en
 * orden hasta encontrar uno que cumpla todo.
 *
 * Retorna null si no hay match (mismo retorno se usa para "no existe",
 * "password incorrecto" y "sub inactiva" — no distinguimos hacia el cliente
 * para evitar oráculos de existencia de cuenta).
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

    const subs = await deps.subscriptions.list({
      customer: raw.id,
      status: "all",
      limit: 10,
    });
    const sub = tieneSubValida(subs.data);
    if (sub) return { customer: raw, subscription: sub };
  }

  return null;
}
