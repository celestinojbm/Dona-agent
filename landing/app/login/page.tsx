// landing/app/login/page.tsx — Acceso.
//
// En pausa (lib/pausa.ts) no hay formulario: muestra la página de pausa.
// Fuera de pausa (sólo la rama staging/despausa-preview) muestra el login real.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";
import { DONA_EN_PAUSA } from "@/lib/pausa";
import LoginForm from "./login-form";

export const metadata: Metadata = {
  title: DONA_EN_PAUSA ? "Dona en pausa" : "Iniciar sesión · Dona",
  robots: { index: false },
};

export default function LoginPage() {
  if (DONA_EN_PAUSA) {
    return <PaginaPausa detalle="El acceso a la cuenta está desactivado durante la pausa." />;
  }
  return <LoginForm />;
}
