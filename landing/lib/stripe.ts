import Stripe from "stripe";

let _stripe: Stripe | null = null;

export function getStripe(): Stripe {
  if (!_stripe) {
    if (!process.env.STRIPE_SECRET_KEY) {
      throw new Error("STRIPE_SECRET_KEY is not set");
    }
    _stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { typescript: true });
  }
  return _stripe;
}

export const PLANS = {
  premium: {
    name: "Premium",
    price: 2000,
    get priceId() { return process.env.STRIPE_PRICE_PREMIUM; },
  },
  pro: {
    name: "Pro",
    price: 4000,
    get priceId() { return process.env.STRIPE_PRICE_PRO; },
  },
} as const;

export type PlanKey = keyof typeof PLANS;

/**
 * T1.7 · Paquetes one-time de créditos (top-ups).
 *
 * Compra puntual sin afectar la suscripción. El usuario se queda con el
 * plan vigente (Premium/Pro) y suma estos créditos al saldo. La compra
 * pasa por checkout mode=payment; el backend la procesa con
 * procesar_evento_stripe (path legacy) que lee metadata.creditos.
 *
 * Cada paquete declara los créditos que entrega y un priceId leído de
 * env. Si la env no está configurada en Vercel, paquete queda
 * deshabilitado (UI lo oculta).
 */
export const PAQUETES = {
  "100": {
    creditos: 100,
    precio_usd: 10,
    label: "100 créditos",
    descripcion: "Para necesidades puntuales",
    get priceId() { return process.env.STRIPE_PRICE_PAQUETE_100; },
  },
  "500": {
    creditos: 500,
    precio_usd: 40,
    label: "500 créditos",
    descripcion: "Mejor relación · 20% extra",
    get priceId() { return process.env.STRIPE_PRICE_PAQUETE_500; },
  },
  "2000": {
    creditos: 2000,
    precio_usd: 120,
    label: "2,000 créditos",
    descripcion: "Para uso intensivo · 33% extra",
    get priceId() { return process.env.STRIPE_PRICE_PAQUETE_2000; },
  },
} as const;

export type PaqueteKey = keyof typeof PAQUETES;
