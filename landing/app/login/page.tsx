// landing/app/login/page.tsx — Acceso durante la pausa.
//
// Sin formulario: el login está desactivado. Además, authorize (auth.ts)
// rechaza cualquier intento sin consultar Stripe ni el backend.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";

export const metadata: Metadata = {
  title: "Dona en pausa",
  robots: { index: false },
};

export default function LoginPage() {
  return <PaginaPausa detalle="El acceso a la cuenta está desactivado durante la pausa." />;
}
