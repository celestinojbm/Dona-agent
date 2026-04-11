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
