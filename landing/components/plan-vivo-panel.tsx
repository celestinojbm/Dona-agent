"use client";

// Panel "Dona trabajando…" del plan vivo (F14). Presentacional: recibe el plan
// (pasos + estado) por props, así es testeable sin red. El wiring de polling
// autenticado (o SSE) al endpoint del plan es aparte.
//
// Accesibilidad: región aria-live="polite", numeración monoespaciada, foco por
// teclado en las filas, estados comunicados con texto (no sólo color); el pulso
// del paso en curso se desactiva con prefers-reduced-motion.

import * as React from "react";

export type EstadoPaso = "pendiente" | "en_curso" | "completado" | "fallido";

export interface PasoPlan {
  id: string;
  titulo: string;
  estado: EstadoPaso;
  resultado?: string;
}

export interface PlanVivo {
  estado: string;
  coste_maximo?: number;
  pasos: PasoPlan[];
}

const ETIQUETA_ESTADO: Record<EstadoPaso, string> = {
  pendiente: "pendiente",
  en_curso: "en curso",
  completado: "hecho",
  fallido: "falló",
};

function Marcador({ estado }: { estado: EstadoPaso }) {
  // aria-hidden: el estado textual va en el <span> con sr-only de la fila.
  if (estado === "completado") {
    return <span aria-hidden className="text-[#00E5B0]">✓</span>;
  }
  if (estado === "fallido") {
    return <span aria-hidden className="text-[#FF5C5C]">!</span>;
  }
  if (estado === "en_curso") {
    return (
      <span
        aria-hidden
        className="inline-block h-2.5 w-2.5 rounded-full bg-[#00E5B0] animate-pulse motion-reduce:animate-none"
      />
    );
  }
  return (
    <span
      aria-hidden
      className="inline-block h-2.5 w-2.5 rounded-full border border-[#6B726F]"
    />
  );
}

export function PlanVivoPanel({ plan }: { plan: PlanVivo }) {
  const trabajando = plan.estado === "en_curso";
  return (
    <section
      aria-label="Plan de la tarea"
      className="w-full max-w-[420px] rounded-2xl border border-white/10 bg-[#0A0A0A] p-6 text-[#F5F7F6]"
    >
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-[20px] font-semibold leading-tight">
          {trabajando ? "Dona trabajando…" : "Plan de la tarea"}
        </h2>
      </header>

      <ol aria-live="polite" className="flex flex-col gap-2">
        {plan.pasos.map((paso, i) => (
          <li
            key={paso.id}
            tabIndex={0}
            className="flex items-start gap-3 rounded-lg px-2 py-2 outline-none focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60"
          >
            <span className="font-mono text-[13px] tabular-nums text-[#A8B0AD]">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="mt-0.5">
              <Marcador estado={paso.estado} />
            </span>
            <span className="flex-1 text-[15px] leading-snug">
              {paso.titulo}
              <span className="sr-only"> — {ETIQUETA_ESTADO[paso.estado]}</span>
              {paso.estado === "fallido" && paso.resultado ? (
                <span className="mt-1 block text-[13px] text-[#FF5C5C]">
                  {paso.resultado}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>

      {plan.coste_maximo ? (
        <p className="mt-4 text-[13px] text-[#A8B0AD]">
          Coste máximo:{" "}
          <span className="font-mono tabular-nums">{plan.coste_maximo}</span> créditos.
        </p>
      ) : null}
    </section>
  );
}

export default PlanVivoPanel;
