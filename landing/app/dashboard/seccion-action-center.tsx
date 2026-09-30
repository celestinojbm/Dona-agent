"use client";

// landing/app/dashboard/seccion-action-center.tsx — T2.1.B
// Action Center · sección del dashboard que muestra acciones recomendadas
// generadas por el Automation Core (T2.1.A). Permite generar, aprobar,
// rechazar y ejecutar (dry-run) acciones según su nivel de riesgo.
//
// Decisiones de UX:
//   - LOW se muestran como "Listas para ejecutar" · botón "Ejecutar".
//   - MEDIUM como "Esperan tu OK" · botones "Aprobar" / "Rechazar".
//   - HIGH como "Requieren aprobación explícita" · se pueden aprobar,
//     pero una HIGH aprobada NO se renderiza como "lista para ejecutar":
//     el estado mostrado es "Aprobada · requiere confirmación dedicada",
//     el ícono es Lock (no Clock) y en el lugar del botón "Ejecutar"
//     aparece un indicador deshabilitado "Confirmación dedicada ·
//     próximamente". T2.2 ya tiene primer ejecutor real, pero no queda
//     expuesto desde este control genérico hasta cerrar UX con preview,
//     costo, riesgo y confirmación fuerte.
//   - CRITICAL aviso fuerte · "Bloqueada · próximo paso: aprobación
//     reforzada futura".
//   - Acciones completed muestran su result_json (renderizado bonito).
//   - Acciones rejected/failed/cancelled aparecen en una sección
//     colapsada "Historial".

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Lock,
  Loader2,
  Play,
  RefreshCw,
} from "lucide-react";
import type {
  AccionAutomatizacion,
  EstadoAccion,
  PerfilEstado,
} from "@/lib/automation-types";
import {
  COPY_CRITICAL_FALLBACK,
  COPY_HIGH_APROBADA_FALLBACK,
  esActiva,
  esTerminal,
  ESTADO_COLOR,
  etiquetaEstadoMostrado,
  RIESGO_COLOR,
  RIESGO_LABEL,
  resolverNextRequiredAction,
} from "@/lib/accion-decision";
import { resumenResultado } from "@/lib/accion-formato";
import {
  MENSAJE_DECISION_INCIERTA,
  mensajeDecision,
  mensajeDeErrorAccion,
  type ResultadoDecision,
} from "@/lib/accion-errores";
import { PanelPreviewHigh, useConfirmacionHigh } from "./confirmacion-high";
import AccionDetalle, {
  type Decision,
  type ResultadoEnvio,
} from "./accion-detalle";

interface AccionesData {
  acciones: AccionAutomatizacion[];
  count: number;
}

interface PerfilDiagInfo {
  estado: PerfilEstado;
  campos_llenos: number;
  campos_totales: number;
  razon: string;
  siguiente_paso: string;
}

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: AccionesData }
  | { status: "error"; code: string };

// Etiquetas, colores y matriz de decisión (estado × riesgo) viven en
// `lib/accion-decision.ts` · las comparten la tarjeta y el panel de
// detalle para no desincronizarse.

// Copy de las confirmaciones de decisión en la tarjeta · deja claro qué
// pasa y qué no pasa antes de llamar al backend.
const COPY_CONFIRMACION_CARD: Record<
  "aprobar" | "rechazar" | "ejecutar",
  { titulo: string; cuerpo: string }
> = {
  aprobar: {
    titulo: "¿Aprobar esta acción?",
    cuerpo:
      "Aprobar habilita el siguiente paso de la acción. No envía nada al exterior por sí solo.",
  },
  rechazar: {
    titulo: "¿Rechazar esta acción?",
    cuerpo:
      "Rechazar es definitivo: la acción pasa al historial y no se puede volver atrás desde aquí.",
  },
  ejecutar: {
    titulo: "¿Ejecutar la acción?",
    cuerpo:
      "La ejecución de este control es dry-run: registra el resultado sin efecto externo real.",
  },
};

export default function SeccionActionCenter() {
  const [load, setLoad] = useState<LoadState>({ status: "idle" });
  const [generando, setGenerando] = useState(false);
  const [accionEnCurso, setAccionEnCurso] = useState<number | null>(null);
  // Hotfix: cuando 'Generar acciones' devuelve 0 acciones, el backend
  // ahora reporta perfil_estado · usamos esto para mostrar al usuario
  // POR QUÉ no se generaron y QUÉ hacer.
  const [perfilDiag, setPerfilDiag] = useState<PerfilDiagInfo | null>(null);
  // Acción abierta en el panel de detalle (null = panel cerrado). Se
  // inicializa desde `?accion=<id>` para que un enlace directo o una
  // recarga de la página reabran el mismo detalle.
  const [detalleId, setDetalleId] = useState<number | null>(leerAccionDeUrl);
  // Destino del foco al cerrar un panel abierto desde la URL (sin botón
  // "Ver detalle" que lo abriera).
  const tituloRef = useRef<HTMLHeadingElement | null>(null);
  // Filtro del historial · "todas" muestra los estados terminales.
  const [filtroHistorial, setFiltroHistorial] = useState<EstadoAccion | "todas">(
    "todas",
  );
  // El historial se controla desde React para que no se cierre solo cada
  // vez que la sección se vuelve a renderizar.
  const [historialAbierto, setHistorialAbierto] = useState(false);
  // Texto que anuncia un lector de pantalla tras una decisión.
  const [aviso, setAviso] = useState("");

  // Devuelve true solo si la lista se recargó · quien acaba de decidir
  // lo usa para no afirmar que el estado mostrado está al día.
  const fetchAcciones = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch("/api/automation/acciones", {
        cache: "no-store",
      });
      // Hotfix: 200 con lista vacía es el caso normal de usuario sin
      // acciones todavía (incluye el caso 'subscription_no_persistida'
      // que el route handler convierte a empty). 4xx/5xx son errores
      // reales del sistema · UI los muestra distinto pero el botón
      // 'Generar acciones' sigue disponible siempre.
      if (!res.ok) {
        const code = `error_${res.status}`;
        setLoad({ status: "error", code });
        return false;
      }
      const data = (await res.json()) as AccionesData;
      setLoad({ status: "ready", data });
      return true;
    } catch {
      setLoad({ status: "error", code: "network_error" });
      return false;
    }
  }, []);

  useEffect(() => {
    setLoad({ status: "loading" });
    void fetchAcciones();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleGenerar() {
    setGenerando(true);
    try {
      const res = await fetch("/api/automation/acciones/generar", {
        method: "POST",
      });
      if (res.status === 404) {
        // Sub no persistida en backend · perfil no se ha creado todavía.
        setPerfilDiag({
          estado: "missing",
          campos_llenos: 0,
          campos_totales: 6,
          razon: "Aún no encontramos tu perfil de negocio.",
          siguiente_paso: (
            "Escribe 'empezar diagnóstico' a Dona por WhatsApp para " +
            "configurar tu negocio. Vuelve aquí cuando termines."
          ),
        });
      } else if (!res.ok) {
        toast.error("No pudimos generar acciones nuevas. Intenta de nuevo.");
      } else {
        // 200 · puede traer perfil_estado del backend
        const data = await res.json();
        if (
          data &&
          typeof data === "object" &&
          data.perfil_estado &&
          data.perfil_estado !== "ready"
        ) {
          setPerfilDiag({
            estado: data.perfil_estado,
            campos_llenos: data.perfil_campos_llenos ?? 0,
            campos_totales: data.perfil_campos_totales ?? 6,
            razon: data.perfil_razon ?? "",
            siguiente_paso: data.perfil_siguiente_paso ?? "",
          });
        } else {
          setPerfilDiag(null);
        }
        await fetchAcciones();
      }
    } catch {
      toast.error("Error de conexión al generar acciones.");
    }
    setGenerando(false);
  }

  // Solo el POST de una decisión · quien llama decide cómo releer el estado.
  const postDecision = useCallback(
    async (accionId: number, op: Decision): Promise<ResultadoEnvio> => {
      setAccionEnCurso(accionId);
      try {
        const res = await fetch(
          `/api/automation/acciones/${accionId}/${op}`,
          { method: "POST" },
        );
        let cuerpo: unknown = null;
        try {
          cuerpo = await res.json();
        } catch {
          // Rutas de error pueden responder sin cuerpo JSON.
          cuerpo = null;
        }
        if (!res.ok) {
          const mensaje = mensajeDeErrorAccion(res.status, cuerpo);
          toast.error(mensaje);
          return { tipo: "rechazada", mensaje };
        }
        return { tipo: "aceptada" };
      } catch {
        // El POST no respondió: la decisión pudo registrarse o no.
        toast.error(MENSAJE_DECISION_INCIERTA);
        return { tipo: "incierta" };
      } finally {
        setAccionEnCurso(null);
      }
    },
    [],
  );

  // Decisión desde la tarjeta · el estado se relee con la lista.
  const handleAccion = useCallback(
    async (accionId: number, op: Decision): Promise<ResultadoDecision> => {
      const envio = await postDecision(accionId, op);
      const estadoActualizado = await fetchAcciones();
      if (envio.tipo === "incierta") {
        setAviso(MENSAJE_DECISION_INCIERTA);
        return { ok: false, mensaje: MENSAJE_DECISION_INCIERTA, estadoActualizado };
      }
      if (envio.tipo === "rechazada") {
        setAviso(envio.mensaje);
        return { ok: false, mensaje: envio.mensaje, estadoActualizado };
      }
      // Decisión registrada ≠ estado actualizado: el mensaje depende de
      // si el GET posterior respondió.
      const mensaje = mensajeDecision(op, estadoActualizado);
      if (!estadoActualizado) toast.warning(mensaje);
      setAviso(mensaje);
      return { ok: true, mensaje, estadoActualizado };
    },
    [fetchAcciones, postDecision],
  );

  const acciones = load.status === "ready" ? load.data.acciones : [];
  const activas = acciones.filter((a) => esActiva(a.estado));
  const historial = acciones.filter((a) => esTerminal(a.estado));
  // Estados terminales realmente presentes · solo se ofrecen filtros con
  // datos, para no llenar la UI de chips vacíos.
  const estadosHistorial = useMemo(
    () =>
      Array.from(new Set(historial.map((a) => a.estado))) as EstadoAccion[],
    [historial],
  );
  const historialFiltrado =
    filtroHistorial === "todas"
      ? historial
      : historial.filter((a) => a.estado === filtroHistorial);
  // Semilla del panel · la acción tal como venía en la lista. El panel la
  // muestra como snapshot mientras hace su propia lectura canónica.
  const semillaDetalle =
    detalleId === null ? null : acciones.find((a) => a.id === detalleId) ?? null;

  // HIGH confirmada desde la tarjeta · mismo criterio que handleAccion.
  const refrescarTrasHighEnTarjeta = useCallback(async () => {
    const estadoActualizado = await fetchAcciones();
    const mensaje = mensajeDecision("high", estadoActualizado);
    if (!estadoActualizado) toast.warning(mensaje);
    setAviso(mensaje);
  }, [fetchAcciones]);

  const abrirDetalle = useCallback((id: number) => {
    setDetalleId(id);
    escribirAccionEnUrl(id);
  }, []);

  const cerrarDetalle = useCallback(() => {
    setDetalleId(null);
    escribirAccionEnUrl(null);
  }, []);

  return (
    <section>
      <h2
        ref={tituloRef}
        tabIndex={-1}
        className="eyebrow mb-6 flex items-center gap-2 focus:outline-none"
      >
        <Sparkles className="w-4 h-4" />
        Centro de acción
      </h2>

      {/* Anuncio para lectores de pantalla de la última decisión.
          aria-live="polite" · no interrumpe lo que el usuario esté
          leyendo. */}
      <p aria-live="polite" role="status" className="sr-only">
        {aviso}
      </p>

      {/* Aviso UX general */}
      <div className="surface-card px-6 py-5 mb-4">
        <p className="text-sm text-[color:var(--ink-2)] leading-relaxed">
          Dona detectó oportunidades para tu negocio. Aquí preparamos
          borradores, planes y checklists.{" "}
          <span className="text-[color:var(--ink)] font-medium">
            Nada se publica ni se envía sin tu aprobación.
          </span>
        </p>
      </div>

      {/* Botón generar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-xs text-[color:var(--muted)]">
          {load.status === "ready"
            ? `${activas.length} acciones activas · ${historial.length} en historial`
            : "Cargando acciones…"}
        </p>
        <button
          onClick={handleGenerar}
          disabled={generando || load.status === "loading"}
          className="btn-ghost px-5 py-2.5 rounded-full text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generando ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          {generando ? "Generando…" : "Generar acciones"}
        </button>
      </div>

      {/* Loading */}
      {load.status === "loading" && (
        <div className="surface-card p-8 text-center">
          <p className="text-[color:var(--muted)]">Cargando…</p>
        </div>
      )}

      {/* Error real (no empty state). El botón 'Generar acciones'
          sigue visible arriba · este panel solo informa la falla y
          ofrece reintento. */}
      {load.status === "error" && (
        <div className="surface-card p-8 border-[#e64263]/40">
          <p className="text-[color:var(--ink-2)]">
            No pudimos cargar tus acciones.
          </p>
          <p className="text-xs text-[color:var(--muted)] mt-1 font-mono">
            {load.code}
          </p>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={fetchAcciones}
              className="btn-ghost px-5 py-2 rounded-full text-sm"
            >
              Reintentar
            </button>
            <button
              onClick={handleGenerar}
              disabled={generando}
              className="btn-primary px-5 py-2 rounded-full text-sm disabled:opacity-50"
            >
              {generando ? "Generando…" : "Generar acciones"}
            </button>
          </div>
        </div>
      )}

      {/* Empty con banner de perfil insuficiente · hotfix
          'action-center-perfil-insuficiente'. Cuando el backend reporta
          perfil_estado != 'ready', mostramos POR QUÉ no se generaron
          acciones y QUÉ hacer. Sin perfilDiag, mostramos el empty
          state genérico. */}
      {load.status === "ready" && acciones.length === 0 && (
        <div className="surface-card p-8">
          {perfilDiag ? (
            <>
              <p className="text-xs uppercase tracking-widest text-amber-700 font-semibold mb-3">
                {perfilDiag.estado === "missing"
                  ? "Diagnóstico pendiente"
                  : "Diagnóstico incompleto"}
              </p>
              <p className="text-[color:var(--ink-2)] mb-2">
                {perfilDiag.razon}
              </p>
              {perfilDiag.estado === "incomplete" && (
                <p className="text-xs text-[color:var(--muted)] mb-3 tabular-nums">
                  {perfilDiag.campos_llenos}/{perfilDiag.campos_totales} campos del diagnóstico llenos
                </p>
              )}
              <p className="text-sm text-[color:var(--ink-2)] mb-4">
                {perfilDiag.siguiente_paso}
              </p>
              <div className="flex items-center gap-2">
                <a
                  href="https://wa.me/?text=empezar%20diagn%C3%B3stico"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary px-5 py-2.5 rounded-full text-sm"
                >
                  Abrir WhatsApp
                </a>
                <button
                  onClick={handleGenerar}
                  disabled={generando}
                  className="btn-ghost px-5 py-2.5 rounded-full text-sm disabled:opacity-50"
                >
                  Reintentar generar
                </button>
              </div>
            </>
          ) : (
            <div className="text-center">
              <p className="text-[color:var(--ink-2)] mb-4">
                Aún no hay acciones generadas.
              </p>
              <button
                onClick={handleGenerar}
                className="btn-primary px-5 py-2.5 rounded-full text-sm"
                disabled={generando}
              >
                Generar acciones desde tu diagnóstico
              </button>
            </div>
          )}
        </div>
      )}

      {/* Activas */}
      {activas.length > 0 && (
        <div className="space-y-4">
          {activas.map((a) => (
              <CardAccion
                key={a.id}
                accion={a}
                enCurso={accionEnCurso === a.id}
                onAprobar={() => handleAccion(a.id, "aprobar")}
                onRechazar={() => handleAccion(a.id, "rechazar")}
                onEjecutar={() => handleAccion(a.id, "ejecutar")}
                onConfirmada={refrescarTrasHighEnTarjeta}
                onConfirmacionFallida={fetchAcciones}
                onVerDetalle={() => abrirDetalle(a.id)}
              />
          ))}
        </div>
      )}

      {/* Historial · solo con estados terminales. El filtro usa los
          estados realmente presentes en los datos. */}
      {historial.length > 0 && (
        <details
          className="mt-8"
          open={historialAbierto}
          onToggle={(ev) => setHistorialAbierto(ev.currentTarget.open)}
        >
          <summary className="cursor-pointer eyebrow mb-3">
            Historial ({historialFiltrado.length}
            {filtroHistorial !== "todas" ? ` de ${historial.length}` : ""})
          </summary>
          <div className="flex flex-wrap items-center gap-2 mt-3 mb-4">
            <FiltroHistorial
              activo={filtroHistorial === "todas"}
              onClick={() => {
                setFiltroHistorial("todas");
                setHistorialAbierto(true);
              }}
            >
              Todas
            </FiltroHistorial>
            {estadosHistorial.map((estado) => (
              <FiltroHistorial
                key={estado}
                activo={filtroHistorial === estado}
                onClick={() => {
                  setFiltroHistorial(estado);
                  setHistorialAbierto(true);
                }}
              >
                {ESTADO_LABEL_FILTRO[estado] ?? estado}
              </FiltroHistorial>
            ))}
          </div>
          {historialFiltrado.length === 0 ? (
            <p className="text-xs text-[color:var(--muted)]">
              No hay acciones en el historial con ese estado.
            </p>
          ) : (
            <div className="space-y-3">
              {historialFiltrado.map((a) => (
                <CardAccion
                  key={a.id}
                  accion={a}
                  enCurso={accionEnCurso === a.id}
                  onAprobar={() => {}}
                  onRechazar={() => {}}
                  onEjecutar={() => {}}
                  onVerDetalle={() => abrirDetalle(a.id)}
                />
              ))}
            </div>
          )}
        </details>
      )}

      {/* Panel de detalle · lectura canónica por id, decisiones solo sobre
          estado verificado. `key` = una instancia por acción. */}
      {detalleId !== null && (
        <AccionDetalle
          key={detalleId}
          id={detalleId}
          semilla={semillaDetalle}
          onCerrar={cerrarDetalle}
          enviarDecision={postDecision}
          onRefrescarLista={fetchAcciones}
          focoSinOrigenRef={tituloRef}
        />
      )}
    </section>
  );
}

// `?accion=<id>` · solo dígitos; cualquier otra cosa se ignora.
function leerAccionDeUrl(): number | null {
  if (typeof window === "undefined") return null;
  const valor = new URLSearchParams(window.location.search).get("accion");
  if (!valor || !/^\d{1,12}$/.test(valor)) return null;
  const id = Number(valor);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function escribirAccionEnUrl(id: number | null) {
  try {
    const url = new URL(window.location.href);
    if (id === null) url.searchParams.delete("accion");
    else url.searchParams.set("accion", String(id));
    window.history.replaceState(window.history.state, "", url.toString());
  } catch {
    // la URL API está siempre en cliente; guard defensivo
  }
}

// Etiquetas cortas para los filtros del historial · reusan el estado
// real de la acción, sin inventar categorías.
const ESTADO_LABEL_FILTRO: Partial<Record<EstadoAccion, string>> = {
  completed: "Completadas",
  rejected: "Rechazadas",
  failed: "Fallidas",
  cancelled: "Canceladas",
};

function FiltroHistorial({
  activo,
  onClick,
  children,
}: {
  activo: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activo}
      className={
        activo
          ? "px-3 py-1 rounded-full text-xs border border-[color:var(--brand)] text-[color:var(--ink)] font-medium"
          : "px-3 py-1 rounded-full text-xs border border-[color:var(--line)] text-[color:var(--muted)]"
      }
    >
      {children}
    </button>
  );
}


interface CardAccionProps {
  accion: AccionAutomatizacion;
  enCurso: boolean;
  onAprobar: () => Promise<ResultadoDecision> | void;
  onRechazar: () => Promise<ResultadoDecision> | void;
  onEjecutar: () => Promise<ResultadoDecision> | void;
  onConfirmada?: () => Promise<void> | void;
  /** Relee la lista si la confirmación HIGH falla o no responde. */
  onConfirmacionFallida?: () => Promise<unknown> | void;
  /** Abre el panel de detalle de esta acción. */
  onVerDetalle?: () => void;
}

function CardAccion({
  accion,
  enCurso,
  onAprobar,
  onRechazar,
  onEjecutar,
  onConfirmada,
  onConfirmacionFallida,
  onVerDetalle,
}: CardAccionProps) {
  const r = accion.riesgo;
  const e = accion.estado;
  // Decisiones irreversibles piden confirmación explícita antes de
  // llamar al backend · mismo patrón en la tarjeta y en el panel.
  const [decisionPendiente, setDecisionPendiente] = useState<
    "aprobar" | "rechazar" | "ejecutar" | null
  >(null);
  // Estado ocupado propio · la tarjeta puede ser la superficie donde se
  // tomó la decisión y necesita decir que está trabajando.
  const [procesando, setProcesando] = useState(false);
  // Foco: al abrir la confirmación el botón que la abrió desaparece, así
  // que movemos el foco al bloque; al cancelar vuelve al disparador.
  const bloqueConfirmRef = useRef<HTMLDivElement | null>(null);
  // Referencias vivas a los disparadores · el botón se re-monta al
  // cerrar la confirmación, así que no se guarda el nodo anterior.
  const refAprobar = useRef<HTMLButtonElement | null>(null);
  const refRechazar = useRef<HTMLButtonElement | null>(null);
  const refEjecutar = useRef<HTMLButtonElement | null>(null);
  const [focoPendiente, setFocoPendiente] = useState<
    "aprobar" | "rechazar" | "ejecutar" | null
  >(null);
  const high = useConfirmacionHigh(
    accion.id,
    onConfirmada,
    onConfirmacionFallida,
  );
  const result = resumenResultado(accion.result_json);
  // Contrato T2.1.B: preferimos el next_required_action que viene del
  // backend · solo caemos al cálculo local cuando el payload es legacy.
  // Esto evita que la UI reimplemente la matriz (estado × riesgo) y se
  // desincronice del backend.
  const { next: nextRequired, motivo: blockReason } = resolverNextRequiredAction(accion);
  // HIGH aprobada NO está "lista para ejecutar": queda pendiente de una
  // UX de confirmación dedicada (preview, costo, riesgo, confirmación
  // fuerte) antes de cualquier efecto externo real. El label y el color
  // del estado deben reflejarlo para que la tarjeta no se confunda con
  // las LOW pending o MEDIUM aprobadas.
  const highAprobadaPendienteConfirmacion =
    nextRequired === "dedicated_confirmation_required";
  const estadoLabelMostrado = etiquetaEstadoMostrado(e, nextRequired);
  const estadoColorMostrado = highAprobadaPendienteConfirmacion
    ? "text-orange-700"
    : ESTADO_COLOR[e];
  const showAprobar =
    nextRequired === "approval_required" && r !== "critical";
  const showEjecutar = nextRequired === "execute_available";
  const showCriticalBlock = nextRequired === "reinforced_approval_required";
  const criticalBlockText = blockReason || COPY_CRITICAL_FALLBACK;
  const dedicatedBlockText = blockReason || COPY_HIGH_APROBADA_FALLBACK;
  const confirmacion = decisionPendiente
    ? COPY_CONFIRMACION_CARD[decisionPendiente]
    : null;

  function ejecutarDecision(d: "aprobar" | "rechazar" | "ejecutar") {
    setDecisionPendiente(null);
    const accion_fn =
      d === "aprobar" ? onAprobar : d === "rechazar" ? onRechazar : onEjecutar;
    void (async () => {
      setProcesando(true);
      try {
        await accion_fn();
      } finally {
        setProcesando(false);
      }
    })();
  }

  // Al abrir la confirmación, el foco va al bloque nuevo · si el usuario
  // cancela, vuelve al botón que la abrió.
  useEffect(() => {
    if (decisionPendiente) bloqueConfirmRef.current?.focus();
  }, [decisionPendiente]);

  // Devuelve el foco al disparador después de volver a montarse.
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

  return (
    <div className="surface-card px-6 py-5">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base font-semibold text-[color:var(--ink)]">
              {accion.titulo}
            </span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${RIESGO_COLOR[r]}`}
            >
              {RIESGO_LABEL[r]}
            </span>
          </div>
          <p className="text-sm text-[color:var(--ink-2)] leading-relaxed">
            {accion.descripcion}
          </p>
          {accion.razon_recomendacion && (
            <p className="text-xs text-[color:var(--muted)] mt-2 italic">
              · {accion.razon_recomendacion}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span
            className={`text-xs flex items-center gap-1.5 ${estadoColorMostrado}`}
          >
            {highAprobadaPendienteConfirmacion ? (
              <Lock className="w-3.5 h-3.5" />
            ) : (
              <IconoEstado estado={e} />
            )}
            {estadoLabelMostrado}
          </span>
          {accion.costo_creditos_estimado > 0 && (
            <span className="text-xs text-[color:var(--muted)] tabular-nums">
              ~{accion.costo_creditos_estimado} créditos
            </span>
          )}
        </div>
      </div>

      {/* Aviso CRITICAL · texto preferentemente del backend
          (execution_block_reason); fallback a copy local si el payload
          es legacy. */}
      {showCriticalBlock && (
        <div className="mt-3 p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
          <p className="text-xs text-[color:var(--dato-neg)] flex items-start gap-2">
            <Lock className="w-4 h-4 mt-0.5 shrink-0" />
            {criticalBlockText}
          </p>
        </div>
      )}

      {/* Aviso HIGH aprobado · texto preferentemente del backend
          (execution_block_reason); fallback a copy local si el payload
          es legacy. */}
      {highAprobadaPendienteConfirmacion && (
        <div className="mt-3 p-3 rounded-lg bg-orange-500/10 border border-orange-500/40">
          <p className="text-xs text-orange-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            {dedicatedBlockText}
          </p>
        </div>
      )}

      {/* Resultado · filas legibles cuando el JSON es plano; el crudo
          queda accesible si no lo es. */}
      {!result.vacio && (e === "completed" || e === "failed") && (
        <div className="mt-3 p-3 rounded-lg bg-[color:var(--bg-soft)] border border-[color:var(--line)]">
          <p className="eyebrow mb-2">
            Resultado
          </p>
          {result.filas.length > 0 ? (
            <dl className="grid gap-1.5">
              {result.filas.map((fila) => (
                <div key={fila.clave} className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
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
                {result.crudo}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* Error */}
      {accion.error_message && (e === "failed" || e === "rejected") && (
        <div className="mt-3 p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
          <p className="text-xs text-[color:var(--dato-neg)]">
            {accion.error_message}
          </p>
        </div>
      )}

      {/* Preview y confirmación HIGH dedicada · bloque compartido con el
          panel de detalle (mismo contrato con el backend). */}
      {highAprobadaPendienteConfirmacion && (
        <PanelPreviewHigh api={high} accionId={accion.id} />
      )}

      {/* Pie · acceso al detalle para cualquier estado + decisiones
          (con confirmación explícita) para las acciones no terminales. */}
      <div className="flex flex-wrap items-center justify-between gap-2 mt-4">
        {onVerDetalle && (
          <button
            type="button"
            onClick={onVerDetalle}
            aria-haspopup="dialog"
            aria-label={`Ver detalle de ${accion.titulo}`}
            className="btn-ghost px-4 py-2 rounded-full text-xs"
          >
            Ver detalle
          </button>
        )}
        {!esTerminal(e) && !confirmacion && (
          <div className="flex flex-wrap items-center justify-end gap-2 ml-auto">
            {showAprobar && (
              <>
                <button
                  ref={refRechazar}
                  onClick={() => setDecisionPendiente("rechazar")}
                  disabled={enCurso || procesando}
                  className="btn-ghost px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Rechazar
                </button>
                <button
                  ref={refAprobar}
                  onClick={() => setDecisionPendiente("aprobar")}
                  disabled={enCurso || procesando}
                  className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                >
                  {enCurso || procesando ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                  Aprobar
                </button>
              </>
            )}
            {showEjecutar && (
              <button
                ref={refEjecutar}
                onClick={() => setDecisionPendiente("ejecutar")}
                disabled={enCurso || procesando}
                className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                {enCurso || procesando ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5" />
                )}
                Ejecutar (dry-run)
              </button>
            )}
            {highAprobadaPendienteConfirmacion && !high.preview && (
              <button
                onClick={high.cargarPreview}
                disabled={enCurso || high.busy}
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
      </div>

      {/* Ocupado · evita que una decisión parezca no haber hecho nada
          mientras el backend responde. */}
      {procesando && (
        <p className="mt-3 text-xs text-[color:var(--muted)] flex items-center gap-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Procesando la decisión…
        </p>
      )}

      {/* Confirmación de la decisión elegida · el backend solo se llama
          cuando el usuario confirma. */}
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
          <div className="flex items-center justify-end gap-2 mt-3">
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
              onClick={() => ejecutarDecision(decisionPendiente)}
              disabled={enCurso}
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
    </div>
  );
}


function IconoEstado({ estado }: { estado: EstadoAccion }) {
  switch (estado) {
    case "pending":
    case "approved":
      return <Clock className="w-3.5 h-3.5" />;
    case "needs_approval":
      return <AlertTriangle className="w-3.5 h-3.5" />;
    case "running":
      return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
    case "completed":
      return <CheckCircle2 className="w-3.5 h-3.5" />;
    case "rejected":
    case "cancelled":
      return <XCircle className="w-3.5 h-3.5" />;
    case "failed":
      return <AlertTriangle className="w-3.5 h-3.5" />;
    default:
      return null;
  }
}
