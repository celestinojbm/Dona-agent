// landing/lib/whatsapp.ts — Envío por Whapi (integración opcional futura).
//
// Apagado: WhatsApp dejó de ser canal principal de la web. Mientras
// WHATSAPP_HABILITADO sea false, no se llama a Whapi aunque exista
// WHAPI_TOKEN. Se conserva para reactivarlo como integración opcional.

import { WHATSAPP_HABILITADO } from "@/lib/whatsapp-opcional";

const WHAPI_TOKEN = process.env.WHAPI_TOKEN;
const WHAPI_URL = "https://gate.whapi.cloud/messages/text";

export async function sendWhatsAppMessage(
  phone: string,
  message: string
): Promise<boolean> {
  if (!WHATSAPP_HABILITADO) return false;
  if (!WHAPI_TOKEN) {
    console.warn("WHAPI_TOKEN not configured — WhatsApp message not sent");
    return false;
  }

  try {
    const res = await fetch(WHAPI_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${WHAPI_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ to: phone, body: message }),
    });

    if (!res.ok) {
      console.error(`WhatsApp send error: ${res.status} — ${await res.text()}`);
      return false;
    }

    return true;
  } catch (err) {
    console.error("WhatsApp send failed:", err);
    return false;
  }
}
