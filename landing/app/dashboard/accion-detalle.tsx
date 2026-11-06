"use client";

// landing/app/dashboard/accion-detalle.tsx
//
// Panel de detalle de una acción del Centro de acción. Cierra el flujo
// central: revisar estado y detalle → decidir (aprobar / rechazar /
// ejecutar) con confirmación explícita → consultar resultado e historial.
//
// Reutiliza los primitivos existentes (`components/ui/sheet.tsx`, Radix
// Dialog): foco atrapado, Escape, aria-modal y devolución de foco al
// cerrar vienen del primitivo; aquí solo se compone el contenido.
//
// Límite real documentado en la propia UI: la API todavía NO expone
// `GET /api/automation/acciones/:id` ni un historial de eventos por
// acción. Todo el detalle se arma con el payload de la lista y con los
// timestamps que ese payload ya trae.

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Lock,
  Play,
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
  etiquetaEstadoMostrado,
  RIESGO_COLOR,
  RIESGO_LABEL,
  resolverNextRequiredAction,
} from "@/lib/accion-decision";
import { lineaTiempoAccion, resumenResultado } from "@/lib/accion-formato";
import {
  mensajeDecision,
  type ResultadoDecision,
} from "@/lib/accion-errores";
import { PanelPreviewHigh, useConfirmacionHigh } from "./confirmacion-high";

type Decision = "aprobar" | "rechazar" | "ejecutar";

interface AccionDetalleProps {
  accion: AccionAutomatizacion | null;
  abierto: boolean;
  /**
   * false cuando `accion` es un snapshot (la lista no se pudo recargar o
   * ya no trae la acción). Con false no se ofrecen decisiones: repetir
   * una decisión sobre un estado viejo puede duplicarla o chocar con el
   * estado real.
   */
  estadoVerificado: boolean;
  /**
   * true cuando la lista se recargó bien pero ya no trae esta acción ·
   * precisa el motivo de `estadoVerificado = false`.
   */
  accionFueraDeLista?: boolean;
  onOpenChange: (abierto: boolean) => void;
  onAprobar: (id: number) => Promise<ResultadoDecision>;
  onRechazar: (id: number) => Promise<ResultadoDecision>;
  onEjecutar: (id: number) => Promise<ResultadoDecision>;
  /** Recarga la lista · true si respondió bien. */
  onRefrescar: () => Promise<boolean>;
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

const COPY_ACTUALIZAR_FALLIDO =
  "Seguimos sin poder cargar el estado de la acción. Intenta de nuevo en unos segundos.";

export default function AccionDetalle({
  accion,
  abierto,
  estadoVerificado,
  accionFueraDeLista = false,
  onOpenChange,
  onAprobar,
  onRechazar,
  onEjecutar,
  onRefrescar,
}: AccionDetalleProps) {
  const [decisionPendiente, setDecisionPendiente] = useState<Decision | null>(null);
  // Estado ocupado del panel · el backend tarda y el usuario debe ver
  // que su decisión se está enviando.
  const [procesando, setProcesando] = useState(false);
  // Resultado de la última decisión tomada en este panel.
  // "aviso": la decisión se registró pero el estado no se pudo recargar.
  const [retro, setRetro] = useState<{
    tipo: "exito" | "aviso" | "error";
    mensaje: string;
  } | null>(null);
  const [actualizando, setActualizando] = useState(false);
  // Foco: al abrir la confirmación el botón que la abrió desaparece, así
  // que movemos el foco al bloque; al cancelar vuelve al disparador.
  const bloqueConfirmRef = useRef<HTMLDivElement | null>(null);
  // Referencias a los disparadores · se re-montan al cerrar la
  // confirmación, así que se enfocan por referencia viva y no guardando
  // el nodo anterior.
  const refAprobar = useRef<HTMLButtonElement | null>(null);
  const refRechazar = useRef<HTMLButtonElement | null>(null);
  const refEjecutar = useRef<HTMLButtonElement | null>(null);
  const [focoPendiente, setFocoPendiente] = useState<Decision | null>(null);
  const idAccion = accion?.id ?? 0;
  // Control que tenía el foco al abrir el panel ("Ver detalle"). El
  // Dialog modal de Radix devuelve el foco a su Trigger, pero aquí el
  // panel se abre por código y no hay Trigger: sin esto el foco cae en
  // body. Layout effect para leerlo antes de que Radix mueva el foco
  // dentro del panel (eso ocurre en un effect normal).
  const focoAlAbrirRef = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    if (abierto && document.activeElement instanceof HTMLElement) {
      focoAlAbrirRef.current = document.activeElement;
    }
  }, [abierto]);
  // Al pasar de verificado a sin verificar (tras una decisión), el botón
  // "Actualizar estado" queda bajo el pliegue en móvil: se lleva a la
  // vista y recibe el foco, porque es el único paso posible.
  const refActualizar = useRef<HTMLButtonElement | null>(null);
  const verificadoAntesRef = useRef(estadoVerificado);
  useEffect(() => {
    const antes = verificadoAntesRef.current;
    verificadoAntesRef.current = estadoVerificado;
    if (abierto && antes && !estadoVerificado && refActualizar.current) {
      refActualizar.current.scrollIntoView({ block: "center" });
      refActualizar.current.focus({ preventScroll: true });
    }
  }, [abierto, estadoVerificado]);
  const high = useConfirmacionHigh(
    idAccion,
    async () => {
      const estadoActualizado = await onRefrescar();
      setRetro({
        tipo: estadoActualizado ? "exito" : "aviso",
        mensaje: mensajeDecision("high", estadoActualizado),
      });
    },
    onRefrescar,
  );

  const decision = accion
    ? resolverNextRequiredAction(accion)
    : { next: "none" as const, motivo: "" };
  const hitos = useMemo(
    () => (accion ? lineaTiempoAccion(accion) : []),
    [accion],
  );
  const resultado = useMemo(
    () => (accion ? resumenResultado(accion.result_json) : null),
    [accion],
  );

  useEffect(() => {
    if (decisionPendiente) bloqueConfirmRef.current?.focus();
  }, [decisionPendiente]);

  // Devuelve el foco al botón que abrió la confirmación una vez que ese
  // botón volvió a montarse.
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

  // Estado efímero del panel · se limpia al cambiar de acción o de
  // apertura para no arrastrar mensajes de otra acción.
  useEffect(() => {
    setDecisionPendiente(null);
    setRetro(null);
  }, [idAccion, abierto]);

  if (!accion) {
    // Radix exige un Root montado · sin acción no hay panel que mostrar.
    return null;
  }

  // Con un snapshot no se ofrece ninguna decisión: primero hay que
  // verificar el estado real.
  const puedeAprobar =
    estadoVerificado &&
    decision.next === "approval_required" &&
    accion.riesgo !== "critical";
  const puedeEjecutar =
    estadoVerificado && decision.next === "execute_available";
  const puedeConfirmarHigh =
    estadoVerificado && decision.next === "dedicated_confirmation_required";
  const bloqueoCritical =
    decision.next === "reinforced_approval_required"
      ? decision.motivo || COPY_CRITICAL_FALLBACK
      : "";
  const bloqueoHigh =
    decision.next === "dedicated_confirmation_required"
      ? decision.motivo || COPY_HIGH_APROBADA_FALLBACK
      : "";
  const terminal = esTerminal(accion.estado);
  const confirmacion = decisionPendiente
    ? COPY_CONFIRMACION[decisionPendiente]
    : null;
  const etiquetaEstado = etiquetaEstadoMostrado(accion.estado, decision.next);
  // El resultado se muestra cuando existe o cuando el estado ya cerró la
  // acción · así un `completed` sin resultado no queda mudo.
  const mostrarResultado =
    resultado !== null &&
    (!resultado.vacio ||
      accion.estado === "completed" ||
      accion.estado === "failed");

  async function ejecutarDecision(d: Decision) {
    setDecisionPendiente(null);
    setRetro(null);
    setProcesando(true);
    try {
      const fn =
        d === "aprobar" ? onAprobar : d === "rechazar" ? onRechazar : onEjecutar;
      const respuesta = await fn(idAccion);
      setRetro({
        tipo: !respuesta.ok
          ? "error"
          : respuesta.estadoActualizado
            ? "exito"
            : "aviso",
        mensaje: respuesta.mensaje,
      });
    } finally {
      setProcesando(false);
    }
  }

  async function actualizarEstado() {
    setActualizando(true);
    try {
      const ok = await onRefrescar();
      // Con la lista recargada, el aviso anterior ya no es cierto.
      setRetro(ok ? null : { tipo: "error", mensaje: COPY_ACTUALIZAR_FALLIDO });
    } finally {
      setActualizando(false);
    }
  }

  return (
    <Sheet open={abierto} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl overflow-y-auto overscroll-contain px-6 py-6 gap-0"
        showClose={false}
        onCloseAutoFocus={(ev) => {
          const destino = focoAlAbrirRef.current;
          if (destino?.isConnected) {
            ev.preventDefault();
            destino.focus();
          }
        }}
      >
        {/* Cabecera fija · el panel es largo y en móvil se pierde el
            contexto al hacer scroll. `-top-6 -mt-6 pt-6` anula el padding
            del contenedor para que no se vea contenido pasando por encima.
            El cierre vive dentro de la cabecera: el de SheetContent es
            absoluto dentro del contenedor con scroll y se iba con él, y a
            ancho completo (móvil) no hay overlay donde tocar para salir. */}
        <div className="sticky -top-6 z-10 -mx-6 -mt-6 px-6 pt-6 pb-3 bg-[color:var(--bg)] border-b border-[color:var(--line)]">
          <SheetClose
            className="absolute right-4 top-4 grid h-9 w-9 cursor-pointer place-items-center rounded-full border border-[color:var(--line)] bg-white text-[color:var(--ink-2)] transition-colors hover:text-[color:var(--ink)]"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </SheetClose>
          <SheetTitle className="text-lg font-semibold text-[color:var(--ink)] pr-12">
            {accion.titulo}
          </SheetTitle>
          <SheetDescription className="text-sm text-[color:var(--ink-2)] mt-1 pr-12">
            Detalle de la acción · {etiquetaEstado}
            {!estadoVerificado && " (sin verificar)"}
          </SheetDescription>

          <div className="flex flex-wrap items-center gap-2 mt-3">
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${RIESGO_COLOR[accion.riesgo]}`}
            >
              Riesgo {RIESGO_LABEL[accion.riesgo]}
            </span>
            <span
              className={`text-xs flex items-center gap-1.5 ${ESTADO_COLOR[accion.estado]}`}
            >
              <IconoEstado estado={accion.estado} />
              {etiquetaEstado}
            </span>
            {accion.costo_creditos_estimado > 0 && (
              <span className="text-xs text-[color:var(--muted)] tabular-nums">
                ~{accion.costo_creditos_estimado} créditos
              </span>
            )}
          </div>
        </div>

        <div aria-busy={procesando} className="pt-4">
          {bloqueoCritical && (
            <div className="p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
              <p className="text-xs text-[color:var(--dato-neg)] flex items-start gap-2">
                <Lock className="w-4 h-4 mt-0.5 shrink-0" />
                {bloqueoCritical}
              </p>
            </div>
          )}
          {bloqueoHigh && (
            <div className="mt-3 p-3 rounded-lg bg-orange-500/10 border border-orange-500/40">
              <p className="text-xs text-orange-700 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                {bloqueoHigh}
              </p>
            </div>
          )}

        <section className="mt-6" aria-labelledby={`detalle-${accion.id}`}>
          <h3 id={`detalle-${accion.id}`} className="eyebrow mb-3">
            Detalle
          </h3>
          <p className="text-sm text-[color:var(--ink-2)] leading-relaxed">
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

        <section className="mt-6">
          <h3 className="eyebrow mb-3">Historial de la acción</h3>
          {hitos.length > 0 ? (
            <ol className="space-y-2">
              {hitos.map((h) => (
                <li key={h.clave} className="flex items-center gap-2 text-xs">
                  <Clock className="w-3.5 h-3.5 text-[color:var(--muted)]" />
                  <span className="text-[color:var(--muted)]">{h.etiqueta}:</span>
                  <span className="text-[color:var(--ink-2)] tabular-nums">
                    {h.valor}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs text-[color:var(--muted)]">
              Esta acción no tiene marcas de tiempo registradas todavía.
            </p>
          )}
          <p className="text-[11px] text-[color:var(--muted)] mt-3 leading-relaxed">
            Estas fechas son las que reporta la acción. La API aún no expone
            un historial de eventos por acción, así que no se muestran pasos
            intermedios.
          </p>
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
            <p className="text-xs text-[color:var(--dato-neg)] p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
              {accion.error_message}
            </p>
          </section>
        )}

        <section className="mt-6">
          <h3 className="eyebrow mb-3">Decisión</h3>

          {/* Resultado de la última decisión tomada EN este panel ·
              error con rol alert (interrumpe), éxito con rol status. */}
          {/* Con la acción fuera de la lista, "la lista ya muestra su
              nuevo estado" sería falso: el aviso de abajo lo sustituye. */}
          {retro && !(accionFueraDeLista && retro.tipo === "exito") && (
            <p
              role={retro.tipo === "error" ? "alert" : "status"}
              className={
                retro.tipo === "exito"
                  ? "text-xs text-emerald-700 p-3 rounded-lg bg-emerald-600/10 border border-emerald-600/40"
                  : retro.tipo === "aviso"
                    ? "text-xs text-amber-800 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40"
                    : "text-xs text-[color:var(--dato-neg)] p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40"
              }
            >
              {retro.mensaje}
            </p>
          )}

          {procesando && (
            <p className="text-xs text-[color:var(--muted)] flex items-center gap-2 mt-3">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Enviando la decisión y actualizando el estado…
            </p>
          )}

          {!estadoVerificado ? (
            <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40">
              {accionFueraDeLista ? (
                <p className="text-xs text-amber-800 leading-relaxed">
                  Esta acción ya no aparece en tu lista: pudo eliminarse o
                  dejar de estar asociada a tu negocio.
                  {retro?.tipo === "exito" &&
                    " Tu última decisión sí quedó registrada antes de eso."}{" "}
                  Lo que ves es su última versión cargada, así que no se
                  ofrecen decisiones sobre ella.
                </p>
              ) : (
                <p className="text-xs text-amber-800 leading-relaxed">
                  No pudimos confirmar el estado actual de esta acción. Lo que
                  ves es la última versión cargada y puede estar desactualizada:
                  las decisiones quedan en pausa hasta actualizarla.
                </p>
              )}
              <button
                type="button"
                ref={refActualizar}
                onClick={() => void actualizarEstado()}
                disabled={actualizando}
                className="btn-ghost mt-3 px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                {actualizando && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Actualizar estado
              </button>
            </div>
          ) : terminal ? (
            <p className="text-xs text-[color:var(--muted)] mt-3">
              Acción cerrada · ya no admite decisiones.
            </p>
          ) : (
            <>
              {!puedeAprobar && !puedeEjecutar && !puedeConfirmarHigh && (
                <p className="text-xs text-[color:var(--muted)] mt-3">
                  No hay una decisión disponible desde este control para el
                  estado actual de la acción.
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
                  <p className="text-sm font-medium text-[color:var(--ink)]">
                    {confirmacion.titulo}
                  </p>
                  <p className="text-xs text-[color:var(--ink-2)] mt-1 leading-relaxed">
                    {confirmacion.cuerpo}
                  </p>
                  <div className="flex flex-wrap items-center justify-end gap-2 mt-3">
                    <button
                      onClick={() => {
                        setFocoPendiente(decisionPendiente);
                        setDecisionPendiente(null);
                      }}
                      className="btn-ghost px-4 py-2 rounded-full text-xs"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => void ejecutarDecision(decisionPendiente)}
                      disabled={procesando}
                      className={
                        decisionPendiente === "rechazar"
                          ? "px-4 py-2 rounded-full text-xs flex items-center gap-1.5 bg-[#e64263]/10 border border-[#e64263]/40 text-[color:var(--dato-neg)] font-medium disabled:opacity-50"
                          : "btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
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
                        ref={refRechazar}
                        onClick={() => setDecisionPendiente("rechazar")}
                        disabled={procesando}
                        className="btn-ghost px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Rechazar
                      </button>
                      <button
                        ref={refAprobar}
                        onClick={() => setDecisionPendiente("aprobar")}
                        disabled={procesando}
                        className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {procesando ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        )}
                        Aprobar
                      </button>
                    </>
                  )}
                  {puedeEjecutar && (
                    <button
                      ref={refEjecutar}
                      onClick={() => setDecisionPendiente("ejecutar")}
                      disabled={procesando}
                      className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                    >
                      {procesando ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      Ejecutar (dry-run)
                    </button>
                  )}
                  {puedeConfirmarHigh && !high.preview && (
                    <button
                      onClick={high.cargarPreview}
                      disabled={procesando || high.busy}
                      className="px-4 py-2 rounded-full text-xs flex items-center gap-1.5 bg-orange-500/10 border border-orange-500/40 text-orange-700 font-medium disabled:opacity-50"
                    >
                      {high.busy ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Lock className="w-3.5 h-3.5" />
                      )}
                      Confirmar envío HIGH
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </section>
        </div>
      </SheetContent>
    </Sheet>
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
      return <Clock className="w-3.5 h-3.5" />;
    case "needs_approval":
    case "failed":
      return <AlertTriangle className="w-3.5 h-3.5" />;
    case "running":
      return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
    case "completed":
      return <CheckCircle2 className="w-3.5 h-3.5" />;
    case "rejected":
    case "cancelled":
      return <XCircle className="w-3.5 h-3.5" />;
    default:
      return null;
  }
}
