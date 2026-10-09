// landing/app/success/page.tsx — Retorno de Stripe durante la pausa.
//
// Esta página NO confirma pagos: llegar aquí no prueba que se haya cobrado
// nada. La conciliación de cierre se hace contra Stripe, no contra la web.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";

export const metadata: Metadata = {
  title: "Dona — plazas completas",
  robots: { index: false },
};

export default function SuccessPage() {
  return (
    <PaginaPausa detalle="Esta página no confirma pagos ni activa suscripciones." />
  );
}
