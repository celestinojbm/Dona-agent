import { NextRequest, NextResponse } from "next/server";
import { getStripe, PLANS, type PlanKey } from "@/lib/stripe";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { plan, phone } = body as { plan?: string; phone?: string };

    if (!plan || !(plan in PLANS)) {
      return NextResponse.json(
        { error: "Invalid plan. Use 'premium' or 'pro'." },
        { status: 400 }
      );
    }

    const selectedPlan = PLANS[plan as PlanKey];
    const origin = req.headers.get("origin") || "http://localhost:3000";

    // If Stripe price IDs are configured, use them (subscription mode)
    // Otherwise, fall back to one-time payment with inline price
    const lineItems = selectedPlan.priceId
      ? [{ price: selectedPlan.priceId, quantity: 1 }]
      : [
          {
            price_data: {
              currency: "usd",
              product_data: { name: `Dona ${selectedPlan.name}` },
              unit_amount: selectedPlan.price,
              recurring: { interval: "month" as const },
            },
            quantity: 1,
          },
        ];

    const session = await getStripe().checkout.sessions.create({
      mode: "subscription",
      payment_method_types: ["card"],
      line_items: lineItems,
      success_url: `${origin}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/cancel`,
      metadata: {
        plan,
        phone: phone || "",
      },
      phone_number_collection: { enabled: true },
    });

    return NextResponse.json({ url: session.url });
  } catch (err: any) {
    console.error("Stripe checkout error:", err);
    return NextResponse.json(
      { error: err.message || "Failed to create checkout session" },
      { status: 500 }
    );
  }
}
