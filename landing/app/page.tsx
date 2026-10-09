// landing/app/page.tsx — Inicio durante la pausa.
//
// Dona está retirada de circulación (ver lib/pausa.ts). La landing comercial
// anterior queda en el historial de git; no se reactiva cambiando un flag:
// el relanzamiento es un PR aparte con producto, precios y cobro aprobados.

import PaginaPausa from "@/components/pagina-pausa";

export default function Home() {
  return <PaginaPausa listaEspera />;
}
