// landing/app/page.tsx — Inicio.
//
// En pausa (main) muestra la página de pausa. Con la pausa apagada —esta
// rama, DONA_EN_PAUSA = false— no hay landing comercial: / manda a /login.
// El relanzamiento comercial sigue siendo un PR aparte.

import { redirect } from "next/navigation";
import PaginaPausa from "@/components/pagina-pausa";
import { DONA_EN_PAUSA } from "@/lib/pausa";

export default function Home() {
  if (DONA_EN_PAUSA) {
    return <PaginaPausa />;
  }
  redirect("/login");
}
