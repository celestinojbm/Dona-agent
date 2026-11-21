// landing/app/dashboard/page.tsx — Dashboard.
//
// En pausa (lib/pausa.ts) no lee la sesión ni monta DashboardClient: una
// sesión anterior (cookie JWT aún válida) no conserva acceso operativo. Fuera
// de pausa (sólo la rama staging/despausa-preview) exige sesión.

import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import PaginaPausa from "@/components/pagina-pausa";
import { DONA_EN_PAUSA } from "@/lib/pausa";
import DashboardClient from "./dashboard-client";

export const metadata: Metadata = {
  title: DONA_EN_PAUSA ? "Dona en pausa" : "Dashboard · Dona",
  robots: { index: false },
};

export default async function DashboardPage() {
  if (DONA_EN_PAUSA) {
    return <PaginaPausa detalle="El acceso a la cuenta está desactivado durante la pausa." />;
  }

  const session = await auth();
  if (!session) {
    redirect("/login");
  }

  return <DashboardClient session={session} />;
}
