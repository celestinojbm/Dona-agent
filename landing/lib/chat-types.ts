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

/**
 * Media OPCIONAL de un turno de chat web (voz/imagen). El naming es IDÉNTICO al
 * contrato del backend (/internal/chat) para que los campos fluyan
 * cliente → /api/chat → bridge → backend SIN remapeo intermedio.
 *
 * - `*_base64` va SIN el prefijo `data:<mime>;base64,` (sólo el payload base64).
 * - Se envía ≥1 de: `mensaje` (texto), `audio_base64`, `imagen_base64`.
 * - Cada adjunto tiene tope de 12 MB decodificados (mismo cap que el backend).
 */
export interface ChatMediaWire {
  audio_base64?: string;
  audio_mime?: string;
  imagen_base64?: string;
  imagen_mime?: string;
  imagen_caption?: string;
}
