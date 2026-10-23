"use client";

// Comparación de modelos lado a lado + chips de sugerencias (F23).
// Presentacional: recibe las respuestas por modelo y las sugerencias por props.
// Estados: vacío (aún sin respuestas), cargando (esqueleto por columna) y error
// por columna. Accesible: cada columna es una región etiquetada por el modelo.

import * as React from "react";

export interface RespuestaComparada {
  modelo: string;
  texto?: string;
  cargando?: boolean;
  error?: string;
}

export interface Sugerencias {
  respuestas: string[];
  acciones: string[];
}

export interface ComparacionModelosProps {
  respuestas: RespuestaComparada[];
  sugerencias?: Sugerencias;
  onElegir?: (modelo: string) => void; // elegir la respuesta ganadora
  onChip?: (texto: string) => void;
}

export function ComparacionModelos({
  respuestas,
  sugerencias,
  onElegir,
  onChip,
}: ComparacionModelosProps) {
  if (respuestas.length === 0) {
    return (
      <p className="rounded-2xl border border-white/10 bg-[#0A0A0A] p-6 text-[15px] text-[#A8B0AD]">
        Elige dos modelos para comparar sus respuestas lado a lado.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {respuestas.map((r) => (
          <section
            key={r.modelo}
            aria-label={`Respuesta de ${r.modelo}`}
            className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-[#0A0A0A] p-4 text-[#F5F7F6]"
          >
            <header className="font-mono text-[13px] text-[#A8B0AD]">{r.modelo}</header>
            {r.cargando ? (
              <div
                aria-label="Cargando"
                className="h-16 animate-pulse rounded-lg bg-white/5 motion-reduce:animate-none"
              />
            ) : r.error ? (
              <p role="alert" className="text-[14px] text-[#FF5C5C]">
                {r.error}
              </p>
            ) : (
              <p className="text-[15px] leading-snug">{r.texto}</p>
            )}
            {!r.cargando && !r.error ? (
              <button
                type="button"
                onClick={() => onElegir?.(r.modelo)}
                className="mt-auto inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#00E5B0] px-4 text-[14px] font-semibold text-[#042019] outline-none focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60"
              >
                Usar esta
              </button>
            ) : null}
          </section>
        ))}
      </div>

      {sugerencias ? (
        <div className="flex flex-col gap-2">
          <ul className="flex flex-wrap gap-2" aria-label="Respuestas sugeridas">
            {sugerencias.respuestas.map((c) => (
              <li key={c}>
                <button
                  type="button"
                  onClick={() => onChip?.(c)}
                  className="inline-flex min-h-[36px] items-center rounded-full border border-white/10 px-3 text-[13px] text-[#F5F7F6] outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60"
                >
                  {c}
                </button>
              </li>
            ))}
          </ul>
          <ul className="flex flex-wrap gap-2" aria-label="Siguientes acciones">
            {sugerencias.acciones.map((c) => (
              <li key={c}>
                <button
                  type="button"
                  onClick={() => onChip?.(c)}
                  className="inline-flex min-h-[36px] items-center rounded-full border border-[#00E5B0]/30 bg-[#00E5B0]/10 px-3 text-[13px] text-[#F5F7F6] outline-none hover:bg-[#00E5B0]/20 focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60"
                >
                  {c}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export default ComparacionModelos;
