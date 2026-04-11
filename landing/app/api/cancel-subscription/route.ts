import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { getStripe } from "@/lib/stripe";

export async function POST() {
  const session = await auth();

  if (!session) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const subscriptionId = (session as any).subscriptionId;

  if (!subscriptionId) {
    return NextResponse.json(
      { error: "No active subscription found" },
      { status: 400 }
    );
  }

  try {
    const canceled = await getStripe().subscriptions.cancel(subscriptionId);
    return NextResponse.json({
      status: canceled.status,
      message: "Subscription canceled successfully",
    });
  } catch (err: any) {
    console.error("Cancel subscription error:", err);
    return NextResponse.json(
      { error: err.message || "Failed to cancel subscription" },
      { status: 500 }
    );
  }
}
