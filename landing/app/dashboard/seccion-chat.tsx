"use client";

// landing/app/dashboard/seccion-chat.tsx
// Chat web con Dona · paridad total con WhatsApp desde el dashboard.
//
// Fase 1 (plataforma web): el usuario habla con Dona desde la web y tiene las
// MISMAS herramientas que por WhatsApp (incluidas pagadas y envíos). El
// mensaje viaja a /api/chat → /internal/chat (backend), que lo procesa con la
// MISMA función que WhatsApp (generar_respuesta), preservando todos los gates.
//
// El historial es compartido web↔WhatsApp por telefono en el backend; esta UI
// muestra sólo los turnos de la sesión web actual (no rehidrata el historial
// completo — eso queda como follow-up junto con streaming SSE).
//
// Decisiones de UX:
//   - Lista de mensajes (usuario / Dona) + input + estado "escribiendo…".
//   - NO-streaming en esta primera versión: spinner mientras espera la
//     respuesta completa. Streaming SSE es follow-up.
//   - Errores del backend se muestran como una "burbuja de sistema" clara, sin
//     tirar la conversación.

import { useCallback, useRef, useState, useEffect } from "react";
import { MessageSquare, Send, Loader2, AlertCircle } from "lucide-react";
import type { ChatResponse, MensajeChat } from "@/lib/chat-types";

// Mapea el `error` del route a un mensaje humano (sin exponer internals).
function mensajeErrorChat(code: string): string {
  switch (code) {
    case "rate_limit":
      return "Vas muy rápido. Espera unos segundos e intenta de nuevo.";
    case "backend_timeout":
      return "Dona tardó demasiado en responder. Intenta de nuevo en un momento.";
    case "subscription_not_found":
    case "subscription_required":
      return "No encontramos tu suscripción activa. Si crees que es un error, escríbenos.";
    case "backend_auth_error":
      return "Hay un problema de configuración en el servidor. Ya estamos al tanto.";
    case "mensaje_vacio":
      return "Escribe un mensaje antes de enviar.";
    case "network_error":
      return "Sin conexión. Verifica tu internet e intenta de nuevo.";
    default:
      return "No pudimos procesar tu mensaje. Intenta de nuevo.";
  }
}

// Turno especial de sistema (error) que se intercala en la lista sin ser
// user ni assistant.
type TurnoUI =
  | { tipo: "mensaje"; mensaje: MensajeChat }
  | { tipo: "error"; texto: string };

export default function SeccionChat() {
  const [turnos, setTurnos] = useState<TurnoUI[]>([]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const finRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll al último turno cuando cambia la lista o el estado de envío.
  // scrollIntoView no existe en jsdom (tests) ni en navegadores muy viejos;
  // el guard evita romper el render en esos entornos.
  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turnos, enviando]);

  const enviar = useCallback(async () => {
    const texto = input.trim();
    if (!texto || enviando) return;

    // Pintar el turno del usuario de inmediato y limpiar el input.
    setTurnos((prev) => [
      ...prev,
      { tipo: "mensaje", mensaje: { rol: "user", texto } },
    ]);
    setInput("");
    setEnviando(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: texto }),
      });
      if (!res.ok) {
        let code = `error_${res.status}`;
        try {
          const errJson = (await res.json()) as { error?: string };
          if (errJson.error) code = errJson.error;
        } catch {
          // ignore parse error
        }
        setTurnos((prev) => [
          ...prev,
          { tipo: "error", texto: mensajeErrorChat(code) },
        ]);
        return;
      }
      const data = (await res.json()) as ChatResponse;
      setTurnos((prev) => [
        ...prev,
        { tipo: "mensaje", mensaje: { rol: "assistant", texto: data.respuesta } },
      ]);
    } catch {
      setTurnos((prev) => [
        ...prev,
        { tipo: "error", texto: mensajeErrorChat("network_error") },
      ]);
    } finally {
      setEnviando(false);
    }
  }, [input, enviando]);

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envía; Shift+Enter hace salto de línea.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void enviar();
    }
  }

  return (
    <section data-tour="chat">
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <MessageSquare className="w-4 h-4" />
        Chat con Dona
      </h2>

      <div className="surface-static overflow-hidden flex flex-col">
        {/* Lista de mensajes */}
        <div className="min-h-[280px] max-h-[520px] overflow-y-auto px-5 py-6 space-y-4">
          {turnos.length === 0 && !enviando && (
            <div className="h-full flex items-center justify-center text-center py-10">
              <p className="text-[color:var(--muted)] max-w-sm">
                Escríbele a Dona como lo harías por WhatsApp. Puede generar
                imágenes, llevar tus números, redactar y enviar correos, y más —
                con los mismos permisos y costos.
              </p>
            </div>
          )}

          {turnos.map((t, i) =>
            t.tipo === "error" ? (
              <BurbujaError key={i} texto={t.texto} />
            ) : (
              <Burbuja key={i} mensaje={t.mensaje} />
            ),
          )}

          {/* Estado "escribiendo…" mientras espera la respuesta completa */}
          {enviando && <BurbujaEscribiendo />}

          <div ref={finRef} />
        </div>

        {/* Input */}
        <div className="border-t border-[color:var(--line)] px-4 py-3 transition-colors focus-within:border-[color:var(--brand)]">
          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Escribe tu mensaje…"
              disabled={enviando}
              className="flex-1 resize-none bg-transparent text-sm text-[color:var(--ink)] placeholder:text-[color:var(--muted)] focus:outline-none py-2 max-h-32 disabled:opacity-50"
            />
            <button
              onClick={() => void enviar()}
              disabled={enviando || !input.trim()}
              aria-label="Enviar mensaje"
              className="btn-primary shrink-0 w-10 h-10 rounded-full flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {enviando ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Burbuja({ mensaje }: { mensaje: MensajeChat }) {
  const esUsuario = mensaje.rol === "user";
  return (
    <div className={`flex ${esUsuario ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
          esUsuario
            ? "bg-[color:var(--fill)] text-[color:var(--ink)]"
            : "bg-[color:var(--bg-soft)] border border-[color:var(--line)] text-[color:var(--ink-2)]"
        }`}
      >
        {mensaje.texto}
      </div>
    </div>
  );
}

function BurbujaError({ texto }: { texto: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-[#e64263]/10 border border-[#e64263]/40 text-[color:var(--dato-neg)] flex items-start gap-2">
        <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
        <span>{texto}</span>
      </div>
    </div>
  );
}

function BurbujaEscribiendo() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl px-4 py-3 bg-[color:var(--bg-soft)] border border-[color:var(--line)] flex items-center gap-2">
        <span className="text-xs text-[color:var(--muted)]">Dona está escribiendo</span>
        <span className="flex gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--muted)] animate-bounce [animation-delay:-0.3s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--muted)] animate-bounce [animation-delay:-0.15s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--muted)] animate-bounce" />
        </span>
      </div>
    </div>
  );
}
