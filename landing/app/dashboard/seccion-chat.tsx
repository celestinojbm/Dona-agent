"use client";

// landing/app/dashboard/seccion-chat.tsx
// Chat web con Dona · paridad total con WhatsApp desde el dashboard.
//
// Fase 1 (plataforma web): el usuario habla con Dona desde la web y tiene las
// MISMAS herramientas que por WhatsApp (incluidas pagadas y envíos). El
// mensaje viaja a /api/chat → /internal/chat (backend), que lo procesa con la
// MISMA función que WhatsApp (generar_respuesta), preservando todos los gates.
//
// Fase 3 (multimodal): además de texto, el usuario puede adjuntar UNA imagen o
// grabar una nota de voz, igual que por WhatsApp. La media viaja en base64 al
// mismo endpoint; el backend transcribe la voz (Whisper) y analiza la imagen
// (Claude Vision) reusando el pipeline de WhatsApp, con el envoltorio
// anti-inyección para el contenido extraído de imágenes.
//
// El historial es compartido web↔WhatsApp por telefono en el backend; esta UI
// muestra sólo los turnos de la sesión web actual (no rehidrata el historial
// completo — eso queda como follow-up junto con streaming SSE).
//
// Decisiones de UX:
//   - Lista de mensajes (usuario / Dona) + composer + estado "escribiendo…".
//   - Un adjunto a la vez (imagen O voz), mostrado como chip sobre el composer;
//     adjuntar/grabar de nuevo lo reemplaza. Espejo del modelo de WhatsApp.
//   - Las imágenes se reducen en el cliente (canvas) antes de subir: menos peso
//     de red, más rápido, y bajo el límite de body de la plataforma.
//   - NO-streaming en esta primera versión: spinner mientras espera la
//     respuesta completa. Streaming SSE es follow-up.
//   - Errores del backend/dispositivo se muestran como una "burbuja de sistema"
//     clara, sin tirar la conversación.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowUp,
  Loader2,
  MessageSquare,
  Mic,
  Paperclip,
  Square,
  X,
} from "lucide-react";
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
      return "Escribe un mensaje o adjunta algo antes de enviar.";
    case "adjunto_invalido":
    case "adjunto_ilegible":
      return "No pudimos leer el archivo. Prueba con otra imagen o graba de nuevo.";
    case "adjunto_demasiado_grande":
      return "El archivo es muy grande (máximo 12 MB). Usa uno más liviano.";
    case "mic_denegado":
      return "No pudimos usar el micrófono. Revisa los permisos del navegador.";
    case "mic_no_soportado":
      return "Tu navegador no permite grabar audio aquí. Escribe o adjunta una imagen.";
    case "network_error":
      return "Sin conexión. Verifica tu internet e intenta de nuevo.";
    default:
      return "No pudimos procesar tu mensaje. Intenta de nuevo.";
  }
}

// Adjunto listo para enviar (un solo adjunto a la vez).
type Adjunto =
  | {
      tipo: "imagen";
      base64: string;
      mime: string;
      nombre: string;
      dataUrl: string;
    }
  | { tipo: "audio"; base64: string; mime: string; duracionSeg: number };

// Representación ligera del adjunto en la burbuja del usuario (ya enviado).
type AdjuntoUI =
  | { tipo: "imagen"; dataUrl: string }
  | { tipo: "audio"; duracionSeg: number };

// Turno especial de sistema (error) que se intercala en la lista sin ser
// user ni assistant.
type TurnoUI =
  | { tipo: "mensaje"; mensaje: MensajeChat; adjunto?: AdjuntoUI }
  | { tipo: "error"; texto: string };

// Sugerencias de arranque (estado vacío): precargan el input. Todas mapean a
// capacidades REALES de Dona por el mismo canal que WhatsApp.
const SUGERENCIAS = [
  "Genera una imagen",
  "Lleva mis números de la semana",
  "Redacta y envía un correo",
  "Resume mis pendientes",
];

// Cap por adjunto (decodificado) · MISMO valor que el backend y el route.
const MAX_MEDIA_BYTES = 12 * 1024 * 1024; // 12 MB
// Lado máximo al reducir imágenes en el cliente + calidad JPEG.
const MAX_IMG_LADO = 1600;
const IMG_CALIDAD = 0.82;
// Corte de seguridad de la grabación (evita notas gigantes).
const MAX_GRAB_SEG = 120;

function formatDuracion(seg: number): string {
  const m = Math.floor(seg / 60);
  const s = Math.max(0, seg) % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** Bytes decodificados de un base64 canónico (sin allocar). */
function base64Bytes(b64: string): number {
  const len = b64.length;
  const pad = b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0;
  return Math.floor((len * 3) / 4) - pad;
}

/** Sólo el payload base64 de un data URL (sin el prefijo `data:...;base64,`). */
function soloBase64(dataUrl: string): string {
  const i = dataUrl.indexOf(",");
  return i >= 0 ? dataUrl.slice(i + 1) : "";
}

function leerComoDataURL(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(typeof fr.result === "string" ? fr.result : "");
    fr.onerror = () => reject(fr.error ?? new Error("read_error"));
    fr.readAsDataURL(blob);
  });
}

/**
 * Reduce la imagen en el cliente (canvas) y devuelve base64 + mime + dataUrl.
 * Si el entorno no soporta canvas/createImageBitmap (p.ej. jsdom en tests) o
 * algo falla, cae a los bytes originales — nunca lanza por eso.
 */
async function comprimirImagen(
  file: File,
): Promise<{ base64: string; mime: string; dataUrl: string }> {
  const raw = await leerComoDataURL(file);
  const rawBase64 = soloBase64(raw);
  const rawMime = file.type || "image/jpeg";
  const original = { base64: rawBase64, mime: rawMime, dataUrl: raw };

  const puedeCanvas =
    typeof document !== "undefined" && typeof createImageBitmap === "function";
  if (!puedeCanvas) return original;

  try {
    const bmp = await createImageBitmap(file);
    const escala = Math.min(1, MAX_IMG_LADO / Math.max(bmp.width, bmp.height));
    const w = Math.max(1, Math.round(bmp.width * escala));
    const h = Math.max(1, Math.round(bmp.height * escala));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      bmp.close?.();
      return original;
    }
    ctx.drawImage(bmp, 0, 0, w, h);
    bmp.close?.();
    const dataUrl = canvas.toDataURL("image/jpeg", IMG_CALIDAD);
    const base64 = soloBase64(dataUrl);
    if (!base64) return original;
    return { base64, mime: "image/jpeg", dataUrl };
  } catch {
    return original;
  }
}

/** Primer mimeType de audio soportado por MediaRecorder ("" = default). */
function elegirMimeAudio(): string {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) {
    return "";
  }
  const candidatos = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  for (const c of candidatos) {
    if (MediaRecorder.isTypeSupported(c)) return c;
  }
  return "";
}

interface SeccionChatProps {
  /** En el shell la sección Chat ocupa todo el alto disponible (estilo
   * WhatsApp Web): la lista crece y el input queda anclado abajo. Sin el
   * prop conserva el layout compacto original (usado por tests y por
   * cualquier embebido futuro). */
  fullHeight?: boolean;
}

export default function SeccionChat({ fullHeight = false }: SeccionChatProps = {}) {
  const [turnos, setTurnos] = useState<TurnoUI[]>([]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [adjunto, setAdjunto] = useState<Adjunto | null>(null);
  const [preparando, setPreparando] = useState(false);
  const [grabando, setGrabando] = useState(false);
  const [segGrabados, setSegGrabados] = useState(0);
  // Voz recién detenida cuyo blob se está leyendo (async) para volverse adjunto.
  // Bloquea el envío/adjuntar en esa ventana (si no, se enviaría un turno que
  // descarta el audio a medio finalizar).
  const [procesandoVoz, setProcesandoVoz] = useState(false);

  const finRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inicioGrabRef = useRef<number>(0);
  // Guard SÍNCRONO de arranque de grabación: cubre la ventana entre el click y
  // que getUserMedia resuelva (donde 'grabando' aún es false).
  const arrancandoRef = useRef(false);

  // Auto-scroll al último turno cuando cambia la lista o el estado de envío.
  // scrollIntoView no existe en jsdom (tests) ni en navegadores muy viejos;
  // el guard evita romper el render en esos entornos.
  useEffect(() => {
    finRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turnos, enviando]);

  const pararStream = useCallback(() => {
    const s = streamRef.current;
    if (s) {
      s.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  // Liberar micrófono / timers al desmontar.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      const rec = mediaRecorderRef.current;
      if (rec && rec.state !== "inactive") {
        try {
          rec.stop();
        } catch {
          // ignore
        }
      }
      const s = streamRef.current;
      if (s) s.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const agregarError = useCallback((code: string) => {
    setTurnos((prev) => [...prev, { tipo: "error", texto: mensajeErrorChat(code) }]);
  }, []);

  const quitarAdjunto = useCallback(() => setAdjunto(null), []);

  // ── Adjuntar imagen ──────────────────────────────────────────────────────
  const abrirSelectorArchivo = useCallback(() => {
    if (enviando || grabando || preparando) return;
    fileInputRef.current?.click();
  }, [enviando, grabando, preparando]);

  const onElegirArchivo = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      // Reset para poder re-elegir el MISMO archivo después.
      e.target.value = "";
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        agregarError("adjunto_invalido");
        return;
      }
      setPreparando(true);
      try {
        const { base64, mime, dataUrl } = await comprimirImagen(file);
        if (!base64) {
          agregarError("adjunto_ilegible");
          return;
        }
        if (base64Bytes(base64) > MAX_MEDIA_BYTES) {
          agregarError("adjunto_demasiado_grande");
          return;
        }
        setAdjunto({
          tipo: "imagen",
          base64,
          mime,
          nombre: file.name || "imagen",
          dataUrl,
        });
      } catch {
        agregarError("adjunto_ilegible");
      } finally {
        setPreparando(false);
      }
    },
    [agregarError],
  );

  // ── Grabar nota de voz ─────────────────────────────────────────────────────

  // Resetea timer + flag de grabación de forma IDEMPOTENTE. Lo llaman TODAS las
  // vías de paro: click de detener, auto-stop por MAX_GRAB_SEG, y el corte
  // externo del track (revocación de permiso / desconexión del micrófono) que
  // dispara onstop SIN pasar por detenerGrabacion. Así el estado queda
  // consistente sin importar cómo terminó la grabación.
  const limpiarEstadoGrabacion = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setGrabando(false);
  }, []);

  const finalizarGrabacion = useCallback(
    async (rec: MediaRecorder) => {
      // onstop es el punto ÚNICO por el que pasa cualquier paro (incluido el
      // corte externo del micrófono): normaliza el estado aquí también.
      limpiarEstadoGrabacion();
      mediaRecorderRef.current = null;
      setProcesandoVoz(true);
      const dur = Math.max(
        1,
        Math.round((Date.now() - inicioGrabRef.current) / 1000),
      );
      const mime = rec.mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type: mime });
      chunksRef.current = [];
      pararStream();
      try {
        if (blob.size === 0) {
          agregarError("adjunto_ilegible");
          return;
        }
        if (blob.size > MAX_MEDIA_BYTES) {
          agregarError("adjunto_demasiado_grande");
          return;
        }
        const dataUrl = await leerComoDataURL(blob);
        const base64 = soloBase64(dataUrl);
        if (!base64) {
          agregarError("adjunto_ilegible");
          return;
        }
        setAdjunto({
          tipo: "audio",
          base64,
          mime: blob.type || mime,
          duracionSeg: dur,
        });
      } catch {
        agregarError("adjunto_ilegible");
      } finally {
        setProcesandoVoz(false);
      }
    },
    [agregarError, limpiarEstadoGrabacion, pararStream],
  );

  const detenerGrabacion = useCallback(() => {
    const rec = mediaRecorderRef.current;
    // Baja timer+flag YA (click/auto). Si hay recorder activo, marca "procesando"
    // de forma síncrona para cerrar la ventana en la que se podría enviar un
    // turno que descarte el audio que aún se está leyendo; onstop lo baja.
    limpiarEstadoGrabacion();
    if (rec && rec.state !== "inactive") {
      setProcesandoVoz(true);
      try {
        rec.stop();
      } catch {
        setProcesandoVoz(false);
      }
    }
  }, [limpiarEstadoGrabacion]);

  const toggleGrabacion = useCallback(async () => {
    if (grabando) {
      detenerGrabacion();
      return;
    }
    if (enviando || preparando || procesandoVoz || arrancandoRef.current) return;
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      agregarError("mic_no_soportado");
      return;
    }
    // Guard síncrono: bloquea un segundo arranque mientras getUserMedia está en
    // vuelo (evita abrir un 2º MediaStream que dejaría el 1º colgado).
    arrancandoRef.current = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = elegirMimeAudio();
      const rec = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      rec.onstop = () => {
        void finalizarGrabacion(rec);
      };
      rec.start();
      mediaRecorderRef.current = rec;
      inicioGrabRef.current = Date.now();
      setSegGrabados(0);
      setGrabando(true);
      timerRef.current = setInterval(() => {
        const s = Math.floor((Date.now() - inicioGrabRef.current) / 1000);
        setSegGrabados(s);
        if (s >= MAX_GRAB_SEG) detenerGrabacion();
      }, 250);
    } catch {
      pararStream();
      agregarError("mic_denegado");
    } finally {
      arrancandoRef.current = false;
    }
  }, [
    grabando,
    enviando,
    preparando,
    procesandoVoz,
    agregarError,
    detenerGrabacion,
    finalizarGrabacion,
    pararStream,
  ]);

  // ── Enviar turno ───────────────────────────────────────────────────────────
  const enviar = useCallback(async () => {
    const texto = input.trim();
    if (enviando || grabando || preparando || procesandoVoz) return;
    if (!texto && !adjunto) return;

    const adjEnviado = adjunto;
    const adjUI: AdjuntoUI | undefined = adjEnviado
      ? adjEnviado.tipo === "imagen"
        ? { tipo: "imagen", dataUrl: adjEnviado.dataUrl }
        : { tipo: "audio", duracionSeg: adjEnviado.duracionSeg }
      : undefined;

    // Pintar el turno del usuario de inmediato y limpiar el composer.
    setTurnos((prev) => [
      ...prev,
      { tipo: "mensaje", mensaje: { rol: "user", texto }, adjunto: adjUI },
    ]);
    setInput("");
    setAdjunto(null);
    setEnviando(true);

    try {
      const payload: Record<string, string> = {};
      if (texto) payload.mensaje = texto;
      if (adjEnviado?.tipo === "imagen") {
        payload.imagen_base64 = adjEnviado.base64;
        payload.imagen_mime = adjEnviado.mime;
      } else if (adjEnviado?.tipo === "audio") {
        payload.audio_base64 = adjEnviado.base64;
        payload.audio_mime = adjEnviado.mime;
      }

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
  }, [input, enviando, grabando, preparando, procesandoVoz, adjunto]);

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envía; Shift+Enter hace salto de línea.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void enviar();
    }
  }

  const puedeEnviar =
    (input.trim().length > 0 || adjunto !== null) && !preparando && !procesandoVoz;

  return (
    <section
      data-tour="chat"
      className={fullHeight ? "flex h-full min-h-0 flex-col" : undefined}
    >
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <MessageSquare className="w-4 h-4" />
        Chat con Dona
      </h2>

      <div
        className={`surface-static overflow-hidden flex flex-col ${
          fullHeight ? "min-h-0 flex-1" : ""
        }`}
      >
        {/* Lista de mensajes */}
        <div
          className={`overflow-y-auto px-5 py-6 space-y-4 ${
            fullHeight ? "flex-1 min-h-0" : "min-h-[280px] max-h-[520px]"
          }`}
        >
          {turnos.length === 0 && !enviando && (
            <div className="flex h-full flex-col items-center justify-center gap-5 py-10 text-center">
              <p className="max-w-sm text-[color:var(--muted)]">
                Escríbele a Dona como lo harías por WhatsApp. Puede generar
                imágenes, llevar tus números, redactar y enviar correos, y más —
                con los mismos permisos y costos.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGERENCIAS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setInput(s);
                      inputRef.current?.focus();
                    }}
                    className="chip-pill cursor-pointer transition-colors hover:border-[color:var(--brand)] hover:text-[color:var(--ink)]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turnos.map((t, i) =>
            t.tipo === "error" ? (
              <BurbujaError key={i} texto={t.texto} />
            ) : (
              <Burbuja key={i} mensaje={t.mensaje} adjunto={t.adjunto} />
            ),
          )}

          {/* Estado "escribiendo…" mientras espera la respuesta completa */}
          {enviando && <BurbujaEscribiendo />}

          <div ref={finRef} />
        </div>

        {/* Composer */}
        <div className="border-t border-[color:var(--line)] p-4">
          <div className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--surface)] shadow-[0_1px_2px_rgba(11,11,18,0.04),0_10px_28px_-22px_rgba(11,11,18,0.25)] transition-colors focus-within:border-[color:var(--brand)]">
            {adjunto && (
              <ChipAdjunto adjunto={adjunto} onQuitar={quitarAdjunto} />
            )}
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Escríbele a Dona…"
              disabled={enviando}
              className="max-h-40 w-full resize-none bg-transparent px-4 pt-3.5 text-[15px] leading-relaxed text-[color:var(--ink)] placeholder:text-[color:var(--muted)] focus:outline-none disabled:opacity-50"
            />
            <div className="flex items-center justify-between gap-2 px-3 pb-3 pt-1.5">
              <div className="flex min-w-0 items-center gap-1">
                <button
                  type="button"
                  onClick={abrirSelectorArchivo}
                  disabled={enviando || grabando || preparando || procesandoVoz}
                  aria-label="Adjuntar imagen"
                  title="Adjuntar imagen"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[color:var(--muted)] transition-colors hover:bg-[color:var(--fill)] hover:text-[color:var(--ink)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {preparando ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Paperclip className="h-4 w-4" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => void toggleGrabacion()}
                  disabled={enviando || preparando || procesandoVoz}
                  aria-label={grabando ? "Detener grabación" : "Grabar nota de voz"}
                  title={grabando ? "Detener grabación" : "Grabar nota de voz"}
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                    grabando
                      ? "bg-[#e64263]/15 text-[color:var(--dato-neg)]"
                      : "text-[color:var(--muted)] hover:bg-[color:var(--fill)] hover:text-[color:var(--ink)]"
                  }`}
                >
                  {grabando ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                </button>
                {grabando ? (
                  <span className="flex items-center gap-1.5 pl-1 text-[11px] text-[color:var(--dato-neg)]">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[color:var(--dato-neg)]" />
                    Grabando · {formatDuracion(segGrabados)}
                  </span>
                ) : (
                  <span className="hidden truncate pl-1 text-[11px] text-[color:var(--muted)] sm:inline">
                    Enter para enviar · Shift+Enter salto de línea
                  </span>
                )}
              </div>
              <button
                onClick={() => void enviar()}
                disabled={enviando || grabando || !puedeEnviar}
                aria-label="Enviar mensaje"
                className="btn-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
              >
                {enviando ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowUp className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
          {/* Input de archivo oculto · lo dispara el botón de adjuntar. */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={onElegirArchivo}
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
          />
        </div>
      </div>
    </section>
  );
}

function ChipAdjunto({
  adjunto,
  onQuitar,
}: {
  adjunto: Adjunto;
  onQuitar: () => void;
}) {
  return (
    <div className="px-3 pt-3">
      <div className="inline-flex max-w-full items-center gap-2 rounded-xl border border-[color:var(--line)] bg-[color:var(--fill)] px-2.5 py-1.5">
        {adjunto.tipo === "imagen" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={adjunto.dataUrl}
            alt={adjunto.nombre}
            className="h-9 w-9 rounded-md object-cover"
          />
        ) : (
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[color:var(--surface)] text-[color:var(--ink-2)]">
            <Mic className="h-4 w-4" />
          </span>
        )}
        <span className="min-w-0 truncate text-xs text-[color:var(--ink-2)] max-w-[180px]">
          {adjunto.tipo === "imagen"
            ? adjunto.nombre
            : `Nota de voz · ${formatDuracion(adjunto.duracionSeg)}`}
        </span>
        <button
          type="button"
          onClick={onQuitar}
          aria-label="Quitar adjunto"
          title="Quitar adjunto"
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[color:var(--muted)] transition-colors hover:bg-[color:var(--surface)] hover:text-[color:var(--ink)]"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function Burbuja({
  mensaje,
  adjunto,
}: {
  mensaje: MensajeChat;
  adjunto?: AdjuntoUI;
}) {
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
        {adjunto?.tipo === "imagen" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={adjunto.dataUrl}
            alt="Imagen enviada"
            className={`max-h-52 max-w-full rounded-lg object-cover ${
              mensaje.texto ? "mb-2" : ""
            }`}
          />
        )}
        {adjunto?.tipo === "audio" && (
          <span
            className={`flex items-center gap-1.5 text-xs opacity-80 ${
              mensaje.texto ? "mb-1" : ""
            }`}
          >
            <Mic className="h-3.5 w-3.5" />
            Nota de voz · {formatDuracion(adjunto.duracionSeg)}
          </span>
        )}
        {mensaje.texto && <span>{mensaje.texto}</span>}
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
