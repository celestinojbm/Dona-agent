// landing/app/dashboard/page.tsx — Dashboard durante la pausa.
//
// No lee la sesión ni monta DashboardClient: una sesión anterior (cookie
// JWT aún válida) no conserva acceso operativo. Las rutas /api/* del
// dashboard también responden 503 antes de mirar la sesión.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";

export const metadata: Metadata = {
  title: "Dona — plazas completas",
  robots: { index: false },
};

export default function DashboardPage() {
  return <PaginaPausa detalle="El acceso a la cuenta está desactivado por ahora." />;
}
