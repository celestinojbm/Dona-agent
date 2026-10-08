// landing/components/aviso-pausa.tsx — Franja de aviso "Dona en pausa".
//
// Se muestra arriba de las páginas que siguen publicadas durante la pausa
// (términos, privacidad). Sin fecha: la fecha histórica de la pausa no se
// afirma en la web hasta que esté confirmada.

import { MENSAJE_PAUSA } from "@/lib/pausa";

export default function AvisoPausa() {
  return (
    <div
      role="status"
      className="w-full border-b border-[color:var(--line)] bg-[color:var(--surface)] px-6 py-3 text-center text-sm text-[color:var(--ink)]"
    >
      {MENSAJE_PAUSA}
    </div>
  );
}
