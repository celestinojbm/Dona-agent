// landing/app/checkout/page.tsx — "Configura tu plan" (Stripe Embedded Checkout)
//
// Wrapper de servidor: exporta metadata y envuelve el cliente en <Suspense>
// (useSearchParams lo exige en Next). Toda la lógica vive en checkout-client.

import { Suspense } from "react";
import type { Metadata } from "next";
import CheckoutClient from "./checkout-client";

export const metadata: Metadata = {
  title: "Configura tu plan — Dona",
  description:
    "Elige tu plan de Dona y paga de forma segura sin salir de la página.",
  robots: { index: false },
};

export default function CheckoutPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[color:var(--bg)]" aria-busy="true" />
      }
    >
      <CheckoutClient />
    </Suspense>
  );
}
