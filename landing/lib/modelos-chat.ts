// landing/lib/modelos-chat.ts — Catálogo de modelos para el selector del chat (F23).
//
// Espejo de agent/multi_model/catalogo.py (_BASE). Es sólo presentación: el
// backend es la fuente de verdad y valida el id. Mantener ambos en sync hasta
// que exista un endpoint que sirva el catálogo.
//
// TODO(F23): el backend aún no expone catálogo ni preferencia por HTTP, y
// /internal/chat (generar_respuesta) no lee la preferencia. Cuando existan,
// reemplazar esta lista por el catálogo del backend y enviar `modelo` en el
// body de /api/chat → chat-bridge → /internal/chat.

import type { ModeloOpcion } from "@/components/selector-modelo";

export const MODELOS_CHAT: ModeloOpcion[] = [
  { id: "claude-sonnet-4-5", nombre: "Claude Sonnet 4.5", proveedor: "anthropic" },
  { id: "claude-haiku-4-5-20251001", nombre: "Claude Haiku 4.5", proveedor: "anthropic" },
  { id: "gpt-4o", nombre: "GPT-4o", proveedor: "openai" },
];

export const MODELO_AUTO = "auto";

/** Nombre legible del modelo elegido (para el botón del composer). */
export function nombreModelo(id: string): string {
  if (id === MODELO_AUTO) return "Auto";
  return MODELOS_CHAT.find((m) => m.id === id)?.nombre ?? id;
}
