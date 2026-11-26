"use client";

// Selector de modelo (F23) — por chat/agente, con modo Automático por defecto.
// Solo recibe modelos que funcionan de verdad (ver lib/modelos-chat.ts); si
// no hay ninguno, el chat no monta este selector y muestra "Automático".
//
// Presentacional: recibe el catálogo y el estado por props (sin red). El cambio
// a mitad de conversación no pierde contexto (el historial vive en el backend y
// es model-agnostic); este control sólo elige qué modelo atiende el próximo turno.
//
// Diseño: hoja clara del sistema (sin panel negro ni verde ajeno a la app).
// El título es un encabezado normal dentro del panel — antes era un <legend>
// de <fieldset>, que el navegador dibuja montado sobre el borde.
//
// Accesibilidad: radiogroup etiquetado por el título, filas de 44 px mínimo,
// foco visible y la selección marcada con texto además del borde.

import * as React from "react";
import { Check } from "lucide-react";

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
  const tituloId = React.useId();
  const opciones: ModeloOpcion[] = [
    { id: "auto", nombre: "Automático", proveedor: "dona" },
    ...modelos,
  ];
  return (
    <div className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--surface)] p-2 shadow-[0_12px_32px_-20px_rgba(11,11,18,0.35)]">
      <p
        id={tituloId}
        className="px-3 pb-1 pt-2 text-[13px] font-medium text-[color:var(--muted)]"
      >
        Modelo de este chat
      </p>
      <div role="radiogroup" aria-labelledby={tituloId} className="flex flex-col gap-1">
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
              className={`flex min-h-11 items-center justify-between gap-3 rounded-xl px-3 py-2 text-left text-[15px] text-[color:var(--ink)] outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[color:var(--ink)]/40 ${
                activo ? "bg-[color:var(--fill)]" : "hover:bg-[color:var(--bg-soft)]"
              }`}
            >
              <span>
                {m.nombre}
                {m.proveedor !== "dona" ? (
                  <span className="ml-2 text-[12px] text-[color:var(--muted)]">{m.proveedor}</span>
                ) : (
                  <span className="block text-[12px] text-[color:var(--muted)]">
                    Dona elige el modelo según la tarea
                  </span>
                )}
              </span>
              <span className="flex shrink-0 items-center gap-2">
                {esRecom ? (
                  <span className="rounded-full border border-[color:var(--line)] px-2 py-0.5 text-[12px] text-[color:var(--ink-2)]">
                    recomendado
                  </span>
                ) : null}
                {activo ? (
                  <Check className="h-4 w-4" aria-label="Seleccionado" />
                ) : null}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default SelectorModelo;
