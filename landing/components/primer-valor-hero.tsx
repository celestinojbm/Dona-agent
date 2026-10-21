"use client";

// Home de primer valor (F12): input hero + chips de acción. Presentacional:
// recibe callbacks por props (sin red). Placeholder "¿Qué quieres lograr hoy?".
// Chips SÓLO de lo implementado. Accesible: label asociado, chips como botones
// con target >=44px y foco visible.

import * as React from "react";

// Decisión de Celestino #11: borrador útil del negocio primero; la imagen se
// ofrece al final.
export const CHIPS_PRIMER_VALOR = [
  "Armar seguimiento",
  "Redactar correo",
  "Programar recordatorio",
  "Ver saldo",
  "Generar imagen",
] as const;

export interface PrimerValorHeroProps {
  chips?: readonly string[];
  onEnviar?: (texto: string) => void;
  onChip?: (chip: string) => void;
}

export function PrimerValorHero({
  chips = CHIPS_PRIMER_VALOR,
  onEnviar,
  onChip,
}: PrimerValorHeroProps) {
  const [texto, setTexto] = React.useState("");
  const id = React.useId();

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    const t = texto.trim();
    if (t) onEnviar?.(t);
  }

  return (
    <section aria-label="¿Qué quieres lograr hoy?" className="w-full max-w-[720px]">
      <form onSubmit={enviar}>
        <label htmlFor={id} className="sr-only">
          ¿Qué quieres lograr hoy?
        </label>
        <input
          id={id}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="¿Qué quieres lograr hoy?"
          className="h-16 w-full rounded-2xl border border-white/10 bg-[#0A0A0A] px-5 text-[17px] text-[#F5F7F6] placeholder:text-[#6B726F] outline-none focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60"
        />
      </form>

      <ul className="mt-4 flex flex-wrap gap-2" aria-label="Acciones rápidas">
        {chips.map((chip) => (
          <li key={chip}>
            <button
              type="button"
              onClick={() => onChip?.(chip)}
              className="inline-flex min-h-[44px] items-center rounded-full border border-[#00E5B0]/30 bg-[#00E5B0]/10 px-4 text-[14px] text-[#F5F7F6] outline-none hover:bg-[#00E5B0]/20 focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60"
            >
              {chip}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default PrimerValorHero;
