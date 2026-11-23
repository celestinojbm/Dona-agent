// landing/app/cancel/page.tsx — Retorno "cancelado" de Stripe durante la pausa.
//
// No afirma nada sobre cargos: la web no lo sabe. La fuente es Stripe.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";

export const metadata: Metadata = {
  title: "Dona — plazas completas",
  robots: { index: false },
};

export default function CancelPage() {
  return <PaginaPausa detalle="No hay planes disponibles: todas las plazas están ocupadas." />;
}
