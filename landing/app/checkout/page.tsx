// landing/app/checkout/page.tsx — Checkout durante la pausa.
//
// No monta Stripe.js ni el formulario embebido: no hay nada que contratar.
// El endpoint /api/checkout también responde 503 sin llamar a Stripe.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";

export const metadata: Metadata = {
  title: "Dona en pausa",
  robots: { index: false },
};

export default function CheckoutPage() {
  return <PaginaPausa detalle="No es posible contratar un plan ni comprar créditos." />;
}
