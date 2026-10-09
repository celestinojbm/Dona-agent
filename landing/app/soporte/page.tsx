// landing/app/soporte/page.tsx — Soporte durante la pausa.
//
// La página anterior publicaba un correo de soporte y prometía cancelar
// desde el dashboard. Ninguna de las dos cosas está verificada hoy: el
// contacto vuelve cuando Celestino confirme que el correo recibe mensajes.

import type { Metadata } from "next";
import PaginaPausa from "@/components/pagina-pausa";

export const metadata: Metadata = {
  title: "Dona en pausa",
};

export default function SoportePage() {
  return <PaginaPausa />;
}
