// landing/lib/chat-types.ts — Tipos compartidos del Chat web (Fase 1)
//
// Los usan tanto el bridge (server-only) como la sección del dashboard
// (client). Por eso viven aparte de chat-bridge.ts (que hace
// `import "server-only"`).

/** Rol de un mensaje en la conversación web (paridad con el historial). */
export type RolChat = "user" | "assistant";

/** Un turno mostrado en la UI del chat. */
export interface MensajeChat {
  rol: RolChat;
  texto: string;
}

/**
 * Respuesta del backend en /internal/chat: sólo el texto de Dona ya generado
 * (mismo pipeline que WhatsApp). NO se auto-envía por WhatsApp; se muestra en
 * la web.
 */
export interface ChatResponse {
  respuesta: string;
}

export interface ChatApiResult {
  ok: boolean;
  status?: number;
  data?: ChatResponse;
  error?: string;
}
