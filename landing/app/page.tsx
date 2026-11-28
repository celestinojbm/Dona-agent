// landing/app/page.tsx — Inicio durante la pausa.
//
// Dona está retirada de circulación (ver lib/pausa.ts). La landing comercial
// anterior queda en el historial de git; no se reactiva cambiando un flag:
// el relanzamiento es un PR aparte con producto, precios y cobro aprobados.
// La presentación de esta ruta usa React Bits; la copia y el estado de pausa
// siguen siendo los de PaginaPausa.

import InicioPublico from "@/components/inicio-publico";

export default function Home() {
  return <InicioPublico />;
}
