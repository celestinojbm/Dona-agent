// landing/app/page.tsx — Landing v2 durante la pausa.
//
// Los CTA («Pedir acceso a la beta») son anclas de esta página. No hay
// formulario ni endpoint nuevo: Dona no acepta compras mientras sigue en pausa.
// Checkout, login, dashboard y el resto de rutas públicas no cambian.

import type { Metadata } from "next";
import PaginaInicio from "@/components/v2/pagina";

export const metadata: Metadata = {
  title: "Dona — Tú decides. Dona ejecuta.",
  description:
    "Dona prepara diagnósticos, oportunidades y acciones reales. Nada sale sin tu permiso. Beta controlada, en pausa: no aceptamos compras nuevas.",
  openGraph: {
    title: "Dona — Tú decides. Dona ejecuta.",
    description:
      "Beta controlada, en pausa. Nada sale sin tu permiso y no aceptamos compras nuevas.",
  },
};

export default function Home() {
  return <PaginaInicio />;
}
