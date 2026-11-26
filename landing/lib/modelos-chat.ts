// landing/lib/modelos-chat.ts — Qué modelos puede elegir el usuario en el chat.
//
// Regla: no se muestra ningún control que no funcione de verdad. Por
// defecto el chat va en "Automático" (Dona elige el modelo en el backend,
// con sus respaldos). Un modelo concreto solo aparece en el selector cuando
// `aplicaEnChat` es true, es decir, cuando /internal/chat lee la elección y
// el modelo responde de verdad.
//
// Estado hoy: el catálogo del backend (agent/multi_model/catalogo.py) existe,
// pero /internal/chat no lee ninguna preferencia de modelo. Por eso todos
// están en false y el usuario solo ve "Automático", sin selector falso.
// Para activar uno: (1) que /api/chat → chat-bridge → /internal/chat envíe
// y aplique `modelo`, (2) poner aplicaEnChat: true aquí, (3) test.

import type { ModeloOpcion } from "@/components/selector-modelo";

export const MODELO_AUTO = "auto";

export interface ModeloCatalogo extends ModeloOpcion {
  /** true solo si el backend aplica esta elección en el chat web. */
  aplicaEnChat: boolean;
}

export const CATALOGO_CHAT: readonly ModeloCatalogo[] = [
  { id: "claude-sonnet-4-5", nombre: "Claude Sonnet 4.5", proveedor: "Anthropic", aplicaEnChat: false },
  { id: "claude-haiku-4-5-20251001", nombre: "Claude Haiku 4.5", proveedor: "Anthropic", aplicaEnChat: false },
  { id: "gpt-4o", nombre: "GPT-4o", proveedor: "OpenAI", aplicaEnChat: false },
];

/** Modelos elegibles de verdad (los que no funcionan quedan ocultos). */
export const MODELOS_CHAT: ModeloOpcion[] = CATALOGO_CHAT.filter(
  (m) => m.aplicaEnChat,
).map(({ id, nombre, proveedor }) => ({ id, nombre, proveedor }));

/** Si no hay ningún modelo elegible, no hay selector: solo "Automático". */
export const HAY_SELECCION_DE_MODELO = MODELOS_CHAT.length > 0;

export function nombreModelo(id: string): string {
  if (id === MODELO_AUTO) return "Automático";
  return MODELOS_CHAT.find((m) => m.id === id)?.nombre ?? "Automático";
}
