// landing/lib/whatsapp-opcional.ts — WhatsApp como integración opcional futura.
//
// WhatsApp deja de ser el canal principal de la web: no aparece en textos,
// tour, chat ni Conexiones. El código de enlace se conserva aquí, apagado,
// para reactivarlo como integración opcional (p. ej. WhatsApp Business para
// hablar con los clientes del negocio) cuando haya decisión de producto.
//
// Es una constante en código, NO una variable de entorno: encenderla exige
// un PR revisado (mismo criterio que lib/pausa.ts).

export const WHATSAPP_HABILITADO = false as const;

const TEXTO_DIAGNOSTICO = "hola Dona, quiero empezar el diagnóstico de mi negocio.";

/**
 * Enlace wa.me con texto pre-llenado (sin envío automático). Solo se usa si
 * WHATSAPP_HABILITADO es true. NEXT_PUBLIC_DONA_WHATSAPP_NUMBER es opcional:
 * sin número, wa.me deja elegir el contacto.
 */
export function urlWhatsApp(texto: string = TEXTO_DIAGNOSTICO): string {
  const num =
    process.env.NEXT_PUBLIC_DONA_WHATSAPP_NUMBER?.trim().replace(/^\+/, "") || "";
  const t = encodeURIComponent(texto);
  if (num && /^\d{10,15}$/.test(num)) return `https://wa.me/${num}?text=${t}`;
  return `https://wa.me/?text=${t}`;
}

const SIGUIENTE_PASO_WEB =
  "Cuéntale a Dona en el chat a qué se dedica tu negocio: qué vendes, a quién y qué te quita más tiempo.";

/**
 * Algunos textos del backend todavía indican "escribe ... por WhatsApp".
 * Con WhatsApp apagado, la web los sustituye por el camino dentro de Dona.
 */
export function siguientePasoSinWhatsApp(texto: string): string {
  if (WHATSAPP_HABILITADO) return texto;
  return /whats\s*app/i.test(texto) ? SIGUIENTE_PASO_WEB : texto;
}
