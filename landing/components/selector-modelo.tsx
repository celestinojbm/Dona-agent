"use client";

// Selector de modelo (F23) — por chat/agente, con modo Auto y modelo recomendado.
// Presentacional: recibe el catálogo y el estado por props (sin red). El cambio
// a mitad de conversación no pierde contexto (el historial vive en el backend y
// es model-agnostic); este control sólo elige qué modelo atiende el próximo turno.
//
// Accesibilidad: radiogroup con roles nativos, foco visible, el modo Auto es una
// opción más del grupo, y el modelo recomendado se marca con texto (no sólo color).

import * as React from "react";

export interface ModeloOpcion {
  id: string;
  nombre: string;
  proveedor: string;
}

export interface SelectorModeloProps {
  modelos: ModeloOpcion[];
  seleccionado: string; // id del modelo o "auto"
  onSeleccionar: (id: string) => void;
  recomendado?: string; // id recomendado por Auto
}

export function SelectorModelo({
  modelos,
  seleccionado,
  onSeleccionar,
  recomendado,
}: SelectorModeloProps) {
  const opciones: ModeloOpcion[] = [
    { id: "auto", nombre: "Auto (elige por tarea y coste)", proveedor: "dona" },
    ...modelos,
  ];
  return (
    <fieldset
      role="radiogroup"
      aria-label="Modelo"
      className="flex flex-col gap-1 rounded-2xl border border-white/10 bg-[#0A0A0A] p-4 text-[#F5F7F6]"
    >
      <legend className="mb-2 px-1 text-[13px] font-medium text-[#A8B0AD]">
        Modelo de este chat
      </legend>
      {opciones.map((m) => {
        const activo = seleccionado === m.id;
        const esRecom = recomendado && m.id === recomendado;
        return (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={activo}
            onClick={() => onSeleccionar(m.id)}
            className="flex min-h-[44px] items-center justify-between gap-3 rounded-lg px-3 text-left text-[15px] outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-[#00E5B0]/60 aria-checked:border aria-checked:border-[#00E5B0]/40 aria-checked:bg-[#00E5B0]/10"
          >
            <span>
              {m.nombre}
              {m.proveedor !== "dona" ? (
                <span className="ml-2 text-[12px] text-[#6B726F]">{m.proveedor}</span>
              ) : null}
            </span>
            {esRecom ? (
              <span className="rounded-full border border-[#00E5B0]/30 bg-[#00E5B0]/10 px-2 py-0.5 text-[12px] text-[#00E5B0]">
                recomendado
              </span>
            ) : null}
          </button>
        );
      })}
    </fieldset>
  );
}

export default SelectorModelo;
