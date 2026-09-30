"use client";

// landing/app/dashboard/accion-detalle.tsx
//
// Panel de detalle de una acción del Centro de acción. Cierra el flujo
// central: revisar estado y detalle → decidir (aprobar / rechazar /
// ejecutar) con confirmación explícita → consultar resultado e historial.
//
// Fuente de verdad: la lectura canónica `GET /api/automation/acciones/:id`
// (ver use-detalle-accion.ts). El panel distingue en pantalla:
//   - Datos actuales   · última lectura canónica, sin nada que la invalide.
//   - Último snapshot  · datos de la lista o de una lectura anterior que
//                        ya no se pudo confirmar. Sirve para leer, no para
//                        decidir.
//   - Eventos comprobados · filas de la bitácora de auditoría de la acción.
//
// Decisiones: solo con estado verificado, y justo antes de enviarlas se
// vuelve a leer la acción; si la lectura falla o el estado cambió, la
// decisión no se envía.
//
// Reutiliza los primitivos existentes (`components/ui/sheet.tsx`, Radix
// Dialog): foco atrapado, Escape y aria-modal vienen del primitivo.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  History,
  Loader2,
  Lock,
  Play,
  RefreshCw,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import type { AccionAutomatizacion } from "@/lib/automation-types";
import {
  COPY_CRITICAL_FALLBACK,
  COPY_HIGH_APROBADA_FALLBACK,
  esTerminal,
  ESTADO_COLOR,
  ESTADO_LABEL,
  etiquetaEstadoMostrado,
  RIESGO_COLOR,
  RIESGO_LABEL,
  resolverNextRequiredAction,
} from "@/lib/accion-decision";
import {
  etiquetaEvento,
  formatearFechaHora,
  formatearFechaHoraSegundos,
  lineaTiempoAccion,
  resumenResultado,
} from "@/lib/accion-formato";
import {
  MENSAJE_DECISION_INCIERTA,
  MENSAJE_ESTADO_CAMBIO_ANTES_DE_ENVIAR,
  MENSAJE_NO_VERIFICADO_ANTES_DE_ENVIAR,
  mensajeDecisionPanel,
  mensajeDecisionSinEfecto,
} from "@/lib/accion-errores";
import { PanelPreviewHigh, useConfirmacionHigh } from "./confirmacion-high";
import { useDetalleAccion, type EstadoDetalle } from "./use-detalle-accion";

export type Decision = "aprobar" | "rechazar" | "ejecutar";

/** Lo que pasó con el POST de una decisión · no dice nada del estado. */
export type ResultadoEnvio =
  | { tipo: "aceptada" }
  | { tipo: "rechazada"; mensaje: string }
  | { tipo: "incierta" };

interface AccionDetalleProps {
  /** Id de la acción · el panel se monta con `key={id}`. */
  id: number;
  /** Acción tal como venía en la lista, si venía · solo para no abrir en blanco. */
  semilla: AccionAutomatizacion | null;
  onCerrar: () => void;
  /** Solo el POST de la decisión · el panel relee el estado por su cuenta. */
  enviarDecision: (id: number, op: Decision) => Promise<ResultadoEnvio>;
  /** Mantiene la lista del Centro de acción al día tras una decisión. */
  onRefrescarLista: () => Promise<unknown>;
  /** Destino del foco al cerrar si el panel se abrió sin disparador (URL). */
  focoSinOrigenRef?: RefObject<HTMLElement | null>;
}

const COPY_CONFIRMACION: Record<Decision, { titulo: string; cuerpo: string }> = {
  aprobar: {
    titulo: "¿Aprobar esta acción?",
    cuerpo:
      "Aprobar habilita el siguiente paso de la acción. No envía nada al exterior por sí solo.",
  },
  rechazar: {
    titulo: "¿Rechazar esta acción?",
    cuerpo:
      "Rechazar es definitivo: la acción queda fuera del flujo activo y pasa al historial. No se puede volver atrás desde aquí.",
  },
  ejecutar: {
    titulo: "¿Ejecutar la acción?",
    cuerpo:
      "La ejecución de este control es dry-run: registra el resultado sin efecto externo real.",
  },
};

// Estado que debe quedar tras una decisión aceptada · si la lectura
// verificada dice otra cosa, el panel no afirma el cambio.
const ESTADO_ESPERADO: Partial<Record<Decision, AccionAutomatizacion["estado"]>> = {
  aprobar: "approved",
  rechazar: "rejected",
};

const COPY_ACTUALIZAR_FALLIDO =
  "Seguimos sin poder cargar el estado de la acción. Intenta de nuevo en unos segundos.";

/** true si lo mostrado al decidir ya no coincide con el estado vigente. */
function cambioRelevante(
  antes: AccionAutomatizacion | null,
  ahora: AccionAutomatizacion,
): boolean {
  if (!antes) return true;
  return (
    antes.estado !== ahora.estado ||
    antes.riesgo !== ahora.riesgo ||
    (antes.next_required_action ?? null) !== (ahora.next_required_action ?? null) ||
    antes.updated_at !== ahora.updated_at
  );
}

export default function AccionDetalle({
  id,
  semilla,
  onCerrar,
  enviarDecision,
  onRefrescarLista,
  focoSinOrigenRef,
}: AccionDetalleProps) {
  const detalle = useDetalleAccion(id, semilla);
  const { estado } = detalle;
  const accion = estado.accion;
  const verificado = estado.fase === "verificado";

  const [decisionPendiente, setDecisionPendiente] = useState<Decision | null>(null);
  // Estado ocupado del panel · verificar + enviar + releer tarda.
  const [procesando, setProcesando] = useState(false);
  // Resultado de la última decisión tomada en este panel.
  // "aviso": la decisión se registró pero el estado no se pudo verificar.
  const [retro, setRetro] = useState<{
    tipo: "exito" | "aviso" | "error";
    mensaje: string;
  } | null>(null);
  const [actualizando, setActualizando] = useState(false);
  // Tras una decisión el control que se usó desaparece: el foco va al
  // siguiente paso útil en vez de caer en el contenedor del diálogo.
  const [destinoFoco, setDestinoFoco] = useState<
    "actualizar" | "retro" | "decision" | null
  >(null);
  const retroRef = useRef<HTMLParagraphElement | null>(null);
  const decisionTituloRef = useRef<HTMLHeadingElement | null>(null);
  // Foco: al abrir la confirmación el botón que la abrió desaparece, así
  // que movemos el foco al bloque; al cancelar vuelve al disparador.
  const bloqueConfirmRef = useRef<HTMLDivElement | null>(null);
  const refAprobar = useRef<HTMLButtonElement | null>(null);
  const refRechazar = useRef<HTMLButtonElement | null>(null);
  const refEjecutar = useRef<HTMLButtonElement | null>(null);
  const refActualizar = useRef<HTMLButtonElement | null>(null);
  const [focoPendiente, setFocoPendiente] = useState<Decision | null>(null);
  // Control que tenía el foco al abrir el panel ("Ver detalle"). El panel
  // se abre por código y no hay Trigger de Radix: sin esto el foco caería
  // en body. Layout effect para leerlo antes de que Radix lo mueva.
  const focoAlAbrirRef = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    if (document.activeElement instanceof HTMLElement) {
      focoAlAbrirRef.current = document.activeElement;
    }
  }, []);

  const high = useConfirmacionHigh(
    id,
    async () => {
      const vigente = await detalle.recargar();
      void onRefrescarLista();
      setRetro({
        tipo: vigente ? "exito" : "aviso",
        mensaje: mensajeDecisionPanel("high", vigente !== null),
      });
      setDestinoFoco(vigente ? "retro" : "actualizar");
    },
    async () => {
      // El envío pudo registrarse o no: se relee antes de ofrecer nada.
      const vigente = await detalle.recargar();
      void onRefrescarLista();
      setDestinoFoco(vigente ? "decision" : "actualizar");
    },
  );

  const decision = accion
    ? resolverNextRequiredAction(accion)
    : { next: "none" as const, motivo: "" };
  const hitos = useMemo(() => (accion ? lineaTiempoAccion(accion) : []), [accion]);
  const resultado = useMemo(
    () => (accion ? resumenResultado(accion.result_json) : null),
    [accion],
  );

  useEffect(() => {
    if (decisionPendiente) bloqueConfirmRef.current?.focus();
  }, [decisionPendiente]);

  // Devuelve el foco al botón que abrió la confirmación una vez montado.
  useEffect(() => {
    if (!focoPendiente) return;
    const ref =
      focoPendiente === "aprobar"
        ? refAprobar
        : focoPendiente === "rechazar"
          ? refRechazar
          : refEjecutar;
    ref.current?.focus();
    setFocoPendiente(null);
  }, [focoPendiente]);

  // Tras una decisión sin estado verificado, "Actualizar estado" es el
  // único paso posible: se lleva a la vista (en móvil queda bajo el
  // pliegue) y recibe el foco. Con estado verificado, el foco va al
  // mensaje de resultado (o al título de la sección si no hay mensaje).
  useEffect(() => {
    if (!destinoFoco || procesando) return;
    const destino =
      destinoFoco === "actualizar"
        ? refActualizar.current
        : destinoFoco === "retro"
          ? retroRef.current ?? decisionTituloRef.current
          : decisionTituloRef.current;
    if (destino) {
      destino.scrollIntoView({ block: "center" });
      destino.focus({ preventScroll: true });
    }
    setDestinoFoco(null);
  }, [destinoFoco, procesando, estado.fase]);

  async function ejecutarDecision(d: Decision) {
    setDecisionPendiente(null);
    setRetro(null);
    setProcesando(true);
    try {
      // 1 · Re-verificar justo antes de enviar: se decide sobre el estado
      // vigente, no sobre el que se leyó al abrir el panel.
      const mostrado = accion;
      const vigente = await detalle.recargar();
      if (!vigente) {
        setRetro({ tipo: "error", mensaje: MENSAJE_NO_VERIFICADO_ANTES_DE_ENVIAR });
        setDestinoFoco("actualizar");
        return;
      }
      if (cambioRelevante(mostrado, vigente)) {
        setRetro({ tipo: "aviso", mensaje: MENSAJE_ESTADO_CAMBIO_ANTES_DE_ENVIAR });
        setDestinoFoco("retro");
        return;
      }
      // 2 · Enviar. Desde aquí lo mostrado deja de estar verificado.
      detalle.invalidar();
      const envio = await enviarDecision(id, d);
      // 3 · Releer el estado real, haya salido como haya salido el POST.
      const despues = await detalle.recargar();
      void onRefrescarLista();
      setDestinoFoco(despues ? "retro" : "actualizar");
      if (envio.tipo === "incierta") {
        setRetro({ tipo: "error", mensaje: MENSAJE_DECISION_INCIERTA });
        return;
      }
      if (envio.tipo === "rechazada") {
        setRetro({ tipo: "error", mensaje: envio.mensaje });
        return;
      }
      const esperado = ESTADO_ESPERADO[d];
      if (despues && esperado && despues.estado !== esperado) {
        setRetro({
          tipo: "aviso",
          mensaje: mensajeDecisionSinEfecto(ESTADO_LABEL[despues.estado]),
        });
        return;
      }
      setRetro({
        tipo: despues ? "exito" : "aviso",
        mensaje: mensajeDecisionPanel(d, despues !== null),
      });
    } finally {
      setProcesando(false);
    }
  }

  async function actualizarEstado() {
    setActualizando(true);
    try {
      const vigente = await detalle.recargar();
      // Con el estado verificado, el aviso anterior ya no es cierto.
      setRetro(vigente ? null : { tipo: "error", mensaje: COPY_ACTUALIZAR_FALLIDO });
    } finally {
      setActualizando(false);
    }
  }

  const cierre = (
    <SheetClose
      className="absolute right-4 top-4 grid h-11 w-11 cursor-pointer place-items-center rounded-full border border-[color:var(--line)] bg-[color:var(--surface)] text-[color:var(--ink-2)] transition-colors hover:text-[color:var(--ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)]"
      aria-label="Cerrar"
    >
      <X className="h-5 w-5" />
    </SheetClose>
  );

  return (
    <Sheet
      open
      onOpenChange={(abierto) => {
        if (!abierto) onCerrar();
      }}
    >
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl overflow-y-auto overscroll-contain px-4 sm:px-6 py-6 gap-0"
        showClose={false}
        aria-busy={estado.fase === "cargando" || procesando}
        onCloseAutoFocus={(ev) => {
          const origen = focoAlAbrirRef.current;
          const destino =
            origen?.isConnected && origen !== document.body
              ? origen
              : focoSinOrigenRef?.current ?? null;
          if (destino?.isConnected) {
            ev.preventDefault();
            destino.focus();
          }
        }}
      >
        {!accion ? (
          <PanelSinDatos
            estado={estado}
            cierre={cierre}
            retro={retro}
            onReintentar={() => void actualizarEstado()}
            reintentando={actualizando}
            onCerrar={onCerrar}
          />
        ) : (
          <>
            {/* Cabecera fija · el panel es largo y en móvil se pierde el
                contexto al hacer scroll. */}
            <div className="sticky -top-6 z-10 -mx-4 sm:-mx-6 -mt-6 px-4 sm:px-6 pt-6 pb-3 bg-[color:var(--bg)] border-b border-[color:var(--line)]">
              {cierre}
              <SheetTitle className="text-lg font-semibold text-[color:var(--ink)] pr-14 break-words">
                {accion.titulo}
              </SheetTitle>
              <SheetDescription className="text-sm text-[color:var(--ink-2)] mt-1 pr-14">
                Detalle de la acción · {etiquetaEstadoMostrado(accion.estado, decision.next)}
                {!verificado && " (sin verificar)"}
              </SheetDescription>

              <div className="flex flex-wrap items-center gap-2 mt-3">
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${RIESGO_COLOR[accion.riesgo]}`}
                >
                  Riesgo {RIESGO_LABEL[accion.riesgo]}
                </span>
                <span
                  className={`text-xs flex items-center gap-1.5 ${ESTADO_COLOR[accion.estado]}`}
                >
                  <IconoEstado estado={accion.estado} />
                  {etiquetaEstadoMostrado(accion.estado, decision.next)}
                </span>
                {accion.costo_creditos_estimado > 0 && (
                  <span className="text-xs text-[color:var(--muted)] tabular-nums">
                    ~{accion.costo_creditos_estimado} créditos
                  </span>
                )}
              </div>
            </div>

            <div className="pt-4">
              <FuenteDatos
                estado={estado}
                procesando={procesando}
                actualizando={actualizando}
                refActualizar={refActualizar}
                onActualizar={() => void actualizarEstado()}
              />

              <ContenidoAccion
                accion={accion}
                verificado={verificado}
                decisionMotivo={decision.motivo}
                decisionNext={decision.next}
                hitos={hitos}
                resultado={resultado}
              />

              <EventosComprobados
                estado={estado}
                onCargarMas={() => void detalle.cargarMasEventos()}
              />

              <section className="mt-8" aria-labelledby={`decision-${accion.id}`}>
                <h3
                  id={`decision-${accion.id}`}
                  ref={decisionTituloRef}
                  tabIndex={-1}
                  className="eyebrow mb-3 focus:outline-none"
                >
                  Decisión
                </h3>

                {/* Resultado de la última decisión tomada EN este panel ·
                    error con rol alert (interrumpe), resto con rol status. */}
                {retro && (
                  <p
                    ref={retroRef}
                    tabIndex={-1}
                    role={retro.tipo === "error" ? "alert" : "status"}
                    className={
                      retro.tipo === "exito"
                        ? "text-xs text-emerald-700 p-3 rounded-lg bg-emerald-600/10 border border-emerald-600/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)]"
                        : retro.tipo === "aviso"
                          ? "text-xs text-amber-800 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)]"
                          : "text-xs text-[color:var(--dato-neg)] p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)]"
                    }
                  >
                    {retro.mensaje}
                  </p>
                )}

                {procesando && (
                  <p className="text-xs text-[color:var(--muted)] flex items-center gap-2 mt-3">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
                    Verificando el estado, enviando la decisión y releyendo la acción…
                  </p>
                )}

                <Decisiones
                  accion={accion}
                  verificado={verificado}
                  procesando={procesando}
                  decisionNext={decision.next}
                  decisionPendiente={decisionPendiente}
                  setDecisionPendiente={setDecisionPendiente}
                  onCancelar={(d) => {
                    setFocoPendiente(d);
                    setDecisionPendiente(null);
                  }}
                  onConfirmar={(d) => void ejecutarDecision(d)}
                  bloqueConfirmRef={bloqueConfirmRef}
                  refAprobar={refAprobar}
                  refRechazar={refRechazar}
                  refEjecutar={refEjecutar}
                  high={high}
                />
              </section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

/** Panel sin acción que mostrar: cargando, ausente (404) o error. */
function PanelSinDatos({
  estado,
  cierre,
  retro,
  onReintentar,
  reintentando,
  onCerrar,
}: {
  estado: EstadoDetalle;
  cierre: React.ReactNode;
  retro: { tipo: string; mensaje: string } | null;
  onReintentar: () => void;
  reintentando: boolean;
  onCerrar: () => void;
}) {
  if (estado.fase === "ausente") {
    return (
      <div className="relative pr-16">
        {cierre}
        <SheetTitle className="text-lg font-semibold text-[color:var(--ink)]">
          Acción no disponible
        </SheetTitle>
        <SheetDescription className="text-sm text-[color:var(--ink-2)] mt-2 leading-relaxed">
          Esta acción no existe o no está asociada a tu cuenta. Puede que el
          enlace sea antiguo o que la acción se haya eliminado.
        </SheetDescription>
        {retro && retro.tipo !== "error" && (
          <p role="status" className="text-xs text-[color:var(--ink-2)] mt-3">
            {retro.mensaje}
          </p>
        )}
        <button
          type="button"
          onClick={onCerrar}
          className="btn-ghost mt-5 px-4 py-2.5 rounded-full text-sm"
        >
          Volver al Centro de acción
        </button>
      </div>
    );
  }
  if (estado.fase === "error") {
    return (
      <div className="relative pr-16">
        {cierre}
        <SheetTitle className="text-lg font-semibold text-[color:var(--ink)]">
          No pudimos cargar la acción
        </SheetTitle>
        <SheetDescription asChild>
          <p
            role="alert"
            className="text-sm text-[color:var(--dato-neg)] mt-2 leading-relaxed"
          >
            {estado.error}
          </p>
        </SheetDescription>
        <button
          type="button"
          onClick={onReintentar}
          disabled={reintentando}
          className="btn-ghost mt-5 px-4 py-2.5 rounded-full text-sm flex items-center gap-2 disabled:opacity-50"
        >
          {reintentando ? (
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="w-4 h-4" aria-hidden />
          )}
          Reintentar
        </button>
      </div>
    );
  }
  return (
    <div className="relative pr-16">
      {cierre}
      <SheetTitle className="text-lg font-semibold text-[color:var(--ink)]">
        Cargando acción
      </SheetTitle>
      <SheetDescription asChild>
        <p
          role="status"
          className="text-sm text-[color:var(--muted)] mt-2 flex items-center gap-2"
        >
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
          Leyendo el estado actual de la acción…
        </p>
      </SheetDescription>
      <div className="mt-6 space-y-3" aria-hidden>
        <div className="h-4 w-2/3 rounded bg-[color:var(--line)] motion-safe:animate-pulse" />
        <div className="h-4 w-1/2 rounded bg-[color:var(--line)] motion-safe:animate-pulse" />
        <div className="h-24 rounded-xl bg-[color:var(--line)] motion-safe:animate-pulse" />
      </div>
    </div>
  );
}

/** Deja claro de dónde salen los datos que se ven y si se puede decidir. */
function FuenteDatos({
  estado,
  procesando,
  actualizando,
  refActualizar,
  onActualizar,
}: {
  estado: EstadoDetalle;
  procesando: boolean;
  actualizando: boolean;
  refActualizar: RefObject<HTMLButtonElement | null>;
  onActualizar: () => void;
}) {
  if (estado.fase === "verificado") {
    return (
      <div className="p-3 rounded-lg bg-emerald-600/10 border border-emerald-600/40">
        <p className="text-xs text-emerald-800 flex items-start gap-2 leading-relaxed">
          <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
          <span>
            <strong className="font-semibold">Datos actuales</strong> · leídos
            del servidor el {formatearFechaHoraSegundos(estado.leidoEn) || "—"}.
            Antes de enviar una decisión se vuelven a verificar.
          </span>
        </p>
      </div>
    );
  }
  if (estado.fase === "cargando" || procesando) {
    return (
      <div className="p-3 rounded-lg bg-[color:var(--bg-soft)] border border-[color:var(--line)]">
        <p className="text-xs text-[color:var(--ink-2)] flex items-start gap-2 leading-relaxed">
          <Loader2 className="w-4 h-4 mt-0.5 shrink-0 animate-spin" aria-hidden />
          <span>
            <strong className="font-semibold">Último snapshot</strong> ·{" "}
            {estado.origen === "lista"
              ? "datos de la lista del Centro de acción"
              : `leído el ${formatearFechaHoraSegundos(estado.leidoEn) || "—"}`}
            . Verificando el estado actual…
          </span>
        </p>
      </div>
    );
  }
  // sin_verificar
  return (
    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/40">
      <p className="text-xs text-amber-800 leading-relaxed">
        <strong className="font-semibold">Último snapshot · sin verificar.</strong>{" "}
        No pudimos confirmar el estado actual de esta acción. Lo que ves{" "}
        {estado.origen === "lista"
          ? "viene de la lista del Centro de acción"
          : `se leyó el ${formatearFechaHoraSegundos(estado.leidoEn) || "—"}`}{" "}
        y puede estar desactualizado: las decisiones quedan en pausa hasta
        actualizarla.
      </p>
      {estado.error && (
        <p className="text-xs text-amber-900 mt-2">{estado.error}</p>
      )}
      <button
        type="button"
        ref={refActualizar}
        onClick={onActualizar}
        disabled={actualizando}
        className="btn-ghost mt-3 px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
      >
        {actualizando ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
        ) : (
          <RefreshCw className="w-3.5 h-3.5" aria-hidden />
        )}
        Actualizar estado
      </button>
    </div>
  );
}

function ContenidoAccion({
  accion,
  verificado,
  decisionMotivo,
  decisionNext,
  hitos,
  resultado,
}: {
  accion: AccionAutomatizacion;
  verificado: boolean;
  decisionMotivo: string;
  decisionNext: ReturnType<typeof resolverNextRequiredAction>["next"];
  hitos: ReturnType<typeof lineaTiempoAccion>;
  resultado: ReturnType<typeof resumenResultado> | null;
}) {
  const bloqueoCritical =
    decisionNext === "reinforced_approval_required"
      ? decisionMotivo || COPY_CRITICAL_FALLBACK
      : "";
  const bloqueoHigh =
    decisionNext === "dedicated_confirmation_required"
      ? decisionMotivo || COPY_HIGH_APROBADA_FALLBACK
      : "";
  const etiquetaEstado = etiquetaEstadoMostrado(accion.estado, decisionNext);
  // El resultado se muestra cuando existe o cuando el estado ya cerró la
  // acción · así un `completed` sin resultado no queda mudo.
  const mostrarResultado =
    resultado !== null &&
    (!resultado.vacio || accion.estado === "completed" || accion.estado === "failed");
  return (
    <>
      {bloqueoCritical && (
        <div className="mt-3 p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
          <p className="text-xs text-[color:var(--dato-neg)] flex items-start gap-2">
            <Lock className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
            {bloqueoCritical}
          </p>
        </div>
      )}
      {bloqueoHigh && (
        <div className="mt-3 p-3 rounded-lg bg-orange-500/10 border border-orange-500/40">
          <p className="text-xs text-orange-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
            {bloqueoHigh}
          </p>
        </div>
      )}

      <section className="mt-6" aria-labelledby={`detalle-${accion.id}`}>
        <h3 id={`detalle-${accion.id}`} className="eyebrow mb-3">
          Detalle
        </h3>
        <p className="text-sm text-[color:var(--ink-2)] leading-relaxed break-words">
          {accion.descripcion}
        </p>
        {accion.razon_recomendacion && (
          <p className="text-xs text-[color:var(--muted)] mt-2 italic">
            · {accion.razon_recomendacion}
          </p>
        )}
        <dl className="grid gap-2 mt-4 text-xs sm:grid-cols-2">
          <Dato etiqueta="Tipo de acción" valor={accion.tipo_accion} />
          <Dato etiqueta="Playbook" valor={accion.playbook_id} />
          <Dato etiqueta="Oportunidad" valor={accion.opportunity_id} />
          <Dato
            etiqueta="Aprobación humana"
            valor={accion.requires_approval ? "Requerida" : "No requerida"}
          />
        </dl>
      </section>

      <section className="mt-6" aria-labelledby={`marcas-${accion.id}`}>
        <h3 id={`marcas-${accion.id}`} className="eyebrow mb-1">
          Marcas de tiempo de la acción
        </h3>
        <p className="text-[11px] text-[color:var(--muted)] mb-3">
          {verificado ? "Según la lectura verificada." : "Según los datos mostrados, sin verificar."}
        </p>
        {hitos.length > 0 ? (
          <ol className="space-y-2">
            {hitos.map((h) => (
              <li key={h.clave} className="flex flex-wrap items-center gap-x-2 text-xs">
                <Clock className="w-3.5 h-3.5 text-[color:var(--muted)]" aria-hidden />
                <span className="text-[color:var(--muted)]">{h.etiqueta}:</span>
                <span className="text-[color:var(--ink-2)] tabular-nums">{h.valor}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-xs text-[color:var(--muted)]">
            Esta acción no tiene marcas de tiempo registradas todavía.
          </p>
        )}
      </section>

      {mostrarResultado && resultado && (
        <section className="mt-6">
          <h3 className="eyebrow mb-3">Resultado</h3>
          {resultado.vacio ? (
            <p className="text-xs text-[color:var(--muted)]">
              La acción quedó en {etiquetaEstado.toLowerCase()} y no registró
              resultado en el payload.
            </p>
          ) : resultado.filas.length > 0 ? (
            <dl className="rounded-lg bg-[color:var(--bg-soft)] border border-[color:var(--line)] divide-y divide-[color:var(--line)]">
              {resultado.filas.map((fila) => (
                <div
                  key={fila.clave}
                  className="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:items-start sm:gap-3"
                >
                  <dt className="text-xs text-[color:var(--muted)] sm:w-40 sm:shrink-0">
                    {fila.clave}
                  </dt>
                  <dd className="text-xs text-[color:var(--ink-2)] break-words">
                    {fila.valor}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <details>
              <summary className="cursor-pointer text-xs text-[color:var(--muted)]">
                Ver resultado sin formato
              </summary>
              <pre className="text-xs text-[color:var(--ink-2)] font-mono whitespace-pre-wrap break-words leading-relaxed mt-2">
                {resultado.crudo}
              </pre>
            </details>
          )}
        </section>
      )}

      {accion.error_message && (
        <section className="mt-6">
          <h3 className="eyebrow mb-3">Error registrado</h3>
          <p className="text-xs text-[color:var(--dato-neg)] p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40 break-words">
            {accion.error_message}
          </p>
        </section>
      )}
    </>
  );
}

/** Bitácora de auditoría de la acción · solo eventos que el backend registró. */
function EventosComprobados({
  estado,
  onCargarMas,
}: {
  estado: EstadoDetalle;
  onCargarMas: () => void;
}) {
  const listaRef = useRef<HTMLOListElement | null>(null);
  // Tras "Cargar eventos anteriores" el botón puede desaparecer: el foco
  // pasa al primer evento nuevo para no perderse en el documento.
  const enfocarDesde = useRef<number | null>(null);
  useEffect(() => {
    const desde = enfocarDesde.current;
    if (desde === null || estado.cargandoMasEventos) return;
    enfocarDesde.current = null;
    const items = listaRef.current?.querySelectorAll<HTMLElement>("li");
    if (items && items.length > desde) items[desde].focus();
  }, [estado.cargandoMasEventos, estado.eventos.length]);

  return (
    <section className="mt-6" aria-labelledby="eventos-comprobados">
      <h3 id="eventos-comprobados" className="eyebrow mb-1 flex items-center gap-2">
        <History className="w-3.5 h-3.5" aria-hidden />
        Eventos comprobados
      </h3>
      <p className="text-[11px] text-[color:var(--muted)] mb-3 leading-relaxed">
        Registros de la bitácora de auditoría de Dona, del más reciente al más
        antiguo. El estado vigente lo define la acción: si el registro de un
        evento falló, puede no aparecer aquí.
        {estado.eventosCargados && estado.fase !== "verificado" && estado.leidoEn && (
          <> Comprobados en la lectura del {formatearFechaHoraSegundos(estado.leidoEn)}.</>
        )}
      </p>
      {!estado.eventosCargados ? (
        estado.fase === "cargando" ? (
          <p className="text-xs text-[color:var(--muted)] flex items-center gap-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
            Cargando eventos…
          </p>
        ) : (
          <p className="text-xs text-[color:var(--muted)]">
            No pudimos cargar la bitácora de esta acción, así que no se
            muestran eventos.
          </p>
        )
      ) : estado.eventos.length === 0 ? (
        <p className="text-xs text-[color:var(--muted)]">
          La bitácora no tiene eventos registrados para esta acción. Las
          acciones anteriores a la bitácora o depuradas por retención no
          conservan eventos.
        </p>
      ) : (
        <ol ref={listaRef} className="relative border-l border-[color:var(--line)] ml-1.5 space-y-3">
          {estado.eventos.map((ev) => {
            const { texto, conocido } = etiquetaEvento(ev.evento);
            const fecha = formatearFechaHora(ev.created_at);
            return (
              <li
                key={ev.id}
                tabIndex={-1}
                className="pl-4 relative focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)] rounded"
              >
                <span
                  aria-hidden
                  className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-[color:var(--ink-2)]"
                />
                <p className="text-xs text-[color:var(--ink)]">
                  {texto}
                  {!conocido && (
                    <code className="ml-1 text-[11px] text-[color:var(--muted)]">
                      {ev.evento}
                    </code>
                  )}
                </p>
                <p className="text-[11px] text-[color:var(--muted)] tabular-nums">
                  {fecha || "Sin fecha registrada"}
                </p>
              </li>
            );
          })}
        </ol>
      )}
      {estado.errorMasEventos && (
        <p role="alert" className="text-xs text-[color:var(--dato-neg)] mt-3">
          {estado.errorMasEventos}
        </p>
      )}
      {estado.eventosCargados && estado.eventosCursor !== null && (
        <button
          type="button"
          onClick={() => {
            enfocarDesde.current = estado.eventos.length;
            onCargarMas();
          }}
          disabled={estado.cargandoMasEventos}
          className="btn-ghost mt-3 px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
        >
          {estado.cargandoMasEventos && (
            <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
          )}
          Cargar eventos anteriores
        </button>
      )}
    </section>
  );
}

function Decisiones({
  accion,
  verificado,
  procesando,
  decisionNext,
  decisionPendiente,
  setDecisionPendiente,
  onCancelar,
  onConfirmar,
  bloqueConfirmRef,
  refAprobar,
  refRechazar,
  refEjecutar,
  high,
}: {
  accion: AccionAutomatizacion;
  verificado: boolean;
  procesando: boolean;
  decisionNext: ReturnType<typeof resolverNextRequiredAction>["next"];
  decisionPendiente: Decision | null;
  setDecisionPendiente: (d: Decision) => void;
  onCancelar: (d: Decision) => void;
  onConfirmar: (d: Decision) => void;
  bloqueConfirmRef: RefObject<HTMLDivElement | null>;
  refAprobar: RefObject<HTMLButtonElement | null>;
  refRechazar: RefObject<HTMLButtonElement | null>;
  refEjecutar: RefObject<HTMLButtonElement | null>;
  high: ReturnType<typeof useConfirmacionHigh>;
}) {
  if (!verificado) {
    return (
      <p className="text-xs text-[color:var(--muted)] mt-3">
        Las decisiones aparecen cuando el estado actual de la acción está
        verificado.
      </p>
    );
  }
  if (esTerminal(accion.estado)) {
    return (
      <p className="text-xs text-[color:var(--muted)] mt-3">
        Acción cerrada · ya no admite decisiones.
      </p>
    );
  }
  const puedeAprobar = decisionNext === "approval_required" && accion.riesgo !== "critical";
  const puedeEjecutar = decisionNext === "execute_available";
  const puedeConfirmarHigh = decisionNext === "dedicated_confirmation_required";
  const confirmacion = decisionPendiente ? COPY_CONFIRMACION[decisionPendiente] : null;
  return (
    <>
      {!puedeAprobar && !puedeEjecutar && !puedeConfirmarHigh && (
        <p className="text-xs text-[color:var(--muted)] mt-3">
          No hay una decisión disponible desde este control para el estado
          actual de la acción.
        </p>
      )}

      <PanelPreviewHigh api={high} accionId={accion.id} />

      {confirmacion && decisionPendiente && (
        <div
          ref={bloqueConfirmRef}
          role="group"
          aria-label={confirmacion.titulo}
          tabIndex={-1}
          className="mt-3 p-4 rounded-xl bg-[color:var(--bg-soft)] border border-[color:var(--line)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand)]"
        >
          <p className="text-sm font-medium text-[color:var(--ink)]">{confirmacion.titulo}</p>
          <p className="text-xs text-[color:var(--ink-2)] mt-1 leading-relaxed">
            {confirmacion.cuerpo}
          </p>
          <div className="flex flex-wrap items-center justify-end gap-2 mt-3">
            <button
              type="button"
              onClick={() => onCancelar(decisionPendiente)}
              className="btn-ghost px-4 py-2.5 rounded-full text-xs"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => onConfirmar(decisionPendiente)}
              disabled={procesando}
              className={
                decisionPendiente === "rechazar"
                  ? "px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 bg-[#e64263]/10 border border-[#e64263]/40 text-[color:var(--dato-neg)] font-medium disabled:opacity-50"
                  : "btn-primary px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              }
            >
              {decisionPendiente === "aprobar" && "Sí, aprobar"}
              {decisionPendiente === "rechazar" && "Sí, rechazar"}
              {decisionPendiente === "ejecutar" && "Sí, ejecutar"}
            </button>
          </div>
        </div>
      )}

      {!confirmacion && (
        <div className="flex flex-wrap items-center gap-2 mt-3">
          {puedeAprobar && (
            <>
              <button
                type="button"
                ref={refRechazar}
                onClick={() => setDecisionPendiente("rechazar")}
                disabled={procesando}
                className="btn-ghost px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                <XCircle className="w-3.5 h-3.5" aria-hidden />
                Rechazar
              </button>
              <button
                type="button"
                ref={refAprobar}
                onClick={() => setDecisionPendiente("aprobar")}
                disabled={procesando}
                className="btn-primary px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5" aria-hidden />
                Aprobar
              </button>
            </>
          )}
          {puedeEjecutar && (
            <button
              type="button"
              ref={refEjecutar}
              onClick={() => setDecisionPendiente("ejecutar")}
              disabled={procesando}
              className="btn-primary px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" aria-hidden />
              Ejecutar (dry-run)
            </button>
          )}
          {puedeConfirmarHigh && !high.preview && (
            <button
              type="button"
              onClick={high.cargarPreview}
              disabled={procesando || high.busy}
              className="px-4 py-2.5 rounded-full text-xs flex items-center gap-1.5 bg-orange-500/10 border border-orange-500/40 text-orange-700 font-medium disabled:opacity-50"
            >
              {high.busy ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
              ) : (
                <Lock className="w-3.5 h-3.5" aria-hidden />
              )}
              Confirmar envío HIGH
            </button>
          )}
        </div>
      )}
    </>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[color:var(--muted)]">{etiqueta}</dt>
      <dd className="text-[color:var(--ink-2)] break-words">{valor || "—"}</dd>
    </div>
  );
}

function IconoEstado({ estado }: { estado: AccionAutomatizacion["estado"] }) {
  switch (estado) {
    case "pending":
    case "approved":
      return <Clock className="w-3.5 h-3.5" aria-hidden />;
    case "needs_approval":
    case "failed":
      return <AlertTriangle className="w-3.5 h-3.5" aria-hidden />;
    case "running":
      return <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />;
    case "completed":
      return <CheckCircle2 className="w-3.5 h-3.5" aria-hidden />;
    case "rejected":
    case "cancelled":
      return <XCircle className="w-3.5 h-3.5" aria-hidden />;
    default:
      return null;
  }
}
