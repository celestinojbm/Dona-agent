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

import { useCallback, useEffect, useState } from "react";
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
  NextRequiredAction,
  NivelRiesgo,
  PerfilEstado,
} from "@/lib/automation-types";

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

const RIESGO_LABEL: Record<NivelRiesgo, string> = {
  low: "Bajo",
  medium: "Medio",
  high: "Alto",
  critical: "Crítico",
};

const RIESGO_COLOR: Record<NivelRiesgo, string> = {
  low: "bg-emerald-500/[0.08] text-emerald-300/90 border-emerald-500/20",
  medium: "bg-amber-500/[0.08] text-amber-300/90 border-amber-500/20",
  high: "bg-orange-500/[0.08] text-orange-300/90 border-orange-500/20",
  critical: "bg-rose-500/[0.08] text-rose-300/90 border-rose-500/20",
};

const ESTADO_LABEL: Record<EstadoAccion, string> = {
  pending: "Lista para ejecutar",
  needs_approval: "Esperando tu aprobación",
  approved: "Aprobada · lista para ejecutar",
  running: "Ejecutando…",
  completed: "Completada",
  rejected: "Rechazada",
  failed: "Falló",
  cancelled: "Cancelada",
};

const ESTADO_COLOR: Record<EstadoAccion, string> = {
  pending: "text-emerald-300/80",
  needs_approval: "text-amber-300/80",
  approved: "text-sky-300/80",
  running: "text-sky-300/80",
  completed: "text-emerald-300/80",
  rejected: "text-white/40",
  failed: "text-rose-300/80",
  cancelled: "text-white/40",
};

function esTerminal(estado: EstadoAccion): boolean {
  return ["completed", "rejected", "failed", "cancelled"].includes(estado);
}

function esActiva(estado: EstadoAccion): boolean {
  return !esTerminal(estado);
}

// Copy local por defecto cuando el backend NO envía
// execution_block_reason (payloads legacy previos al contrato). Mantiene
// la UX anterior intacta para clientes que aún no leen el contrato.
const COPY_HIGH_APROBADA_FALLBACK =
  "Esta acción es de alto impacto. Está aprobada, pero necesita " +
  "confirmación dedicada antes de ejecutar un efecto externo real.";
const COPY_CRITICAL_FALLBACK =
  "Esta acción es crítica. Requiere confirmación reforzada y aún no " +
  "puede ejecutarse automáticamente.";

// Fallback local que reimplementa el mismo contrato de
// `agent.automation.permissions.calcular_next_required_action`. Solo se
// usa cuando el payload viene sin el contrato (acciones serializadas por
// versiones previas del backend). Mientras backend mande
// next_required_action, este helper no se ejecuta.
function calcularNextRequiredActionLocal(
  estado: EstadoAccion,
  riesgo: NivelRiesgo,
): { next: NextRequiredAction; motivo: string } {
  if (
    estado === "completed" ||
    estado === "rejected" ||
    estado === "failed" ||
    estado === "cancelled" ||
    estado === "running"
  ) {
    return { next: "none", motivo: "" };
  }
  if (riesgo === "critical") {
    return { next: "reinforced_approval_required", motivo: COPY_CRITICAL_FALLBACK };
  }
  if (riesgo === "high") {
    if (estado === "approved") {
      return {
        next: "dedicated_confirmation_required",
        motivo: COPY_HIGH_APROBADA_FALLBACK,
      };
    }
    if (estado === "needs_approval") {
      return { next: "approval_required", motivo: "" };
    }
    return { next: "none", motivo: "" };
  }
  // low / medium · cada riesgo abre ejecución solo si su estado lo
  // justifica. LOW puede auto-ejecutar desde pending; MEDIUM exige
  // aprobación humana primero · pending/medium aquí solo ocurre por
  // datos legacy o un bug, y NO se debe ofrecer ningún control genérico
  // (TRANSICIONES backend sólo permite pending → running/cancelled/
  // rejected, así que aprobar desde pending sería transición inválida).
  if (estado === "needs_approval") {
    return { next: "approval_required", motivo: "" };
  }
  if (riesgo === "low" && (estado === "pending" || estado === "approved")) {
    return { next: "execute_available", motivo: "" };
  }
  if (riesgo === "medium" && estado === "approved") {
    return { next: "execute_available", motivo: "" };
  }
  return { next: "none", motivo: "" };
}

function resolverNextRequiredAction(
  accion: AccionAutomatizacion,
): { next: NextRequiredAction; motivo: string } {
  const fromApi = accion.next_required_action;
  if (fromApi) {
    return {
      next: fromApi,
      motivo: accion.execution_block_reason ?? "",
    };
  }
  return calcularNextRequiredActionLocal(accion.estado, accion.riesgo);
}

function safeParseJson(s: string): Record<string, unknown> | null {
  try {
    const v = JSON.parse(s);
    if (v && typeof v === "object") return v as Record<string, unknown>;
    return null;
  } catch {
    return null;
  }
}

export default function SeccionActionCenter() {
  const [load, setLoad] = useState<LoadState>({ status: "idle" });
  const [generando, setGenerando] = useState(false);
  const [accionEnCurso, setAccionEnCurso] = useState<number | null>(null);
  // Hotfix: cuando 'Generar acciones' devuelve 0 acciones, el backend
  // ahora reporta perfil_estado · usamos esto para mostrar al usuario
  // POR QUÉ no se generaron y QUÉ hacer.
  const [perfilDiag, setPerfilDiag] = useState<PerfilDiagInfo | null>(null);

  const fetchAcciones = useCallback(async () => {
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
        return;
      }
      const data = (await res.json()) as AccionesData;
      setLoad({ status: "ready", data });
    } catch {
      setLoad({ status: "error", code: "network_error" });
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
        alert("No pudimos generar acciones nuevas. Intenta de nuevo.");
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
      alert("Error de conexión al generar acciones.");
    }
    setGenerando(false);
  }

  async function handleAccion(
    accionId: number,
    op: "aprobar" | "rechazar" | "ejecutar",
  ) {
    setAccionEnCurso(accionId);
    try {
      const res = await fetch(
        `/api/automation/acciones/${accionId}/${op}`,
        { method: "POST" },
      );
      if (!res.ok) {
        alert(`No pudimos ${op} esta acción. Intenta de nuevo.`);
      }
      await fetchAcciones();
    } catch {
      alert("Error de conexión.");
    }
    setAccionEnCurso(null);
  }

  const acciones = load.status === "ready" ? load.data.acciones : [];
  const activas = acciones.filter((a) => esActiva(a.estado));
  const historial = acciones.filter((a) => esTerminal(a.estado));

  return (
    <section>
      <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
        <Sparkles className="w-4 h-4" />
        Centro de acción
      </h2>

      {/* Aviso UX general */}
      <div className="glass-card rounded-2xl px-6 py-5 mb-4 border-white/[0.06]">
        <p className="text-sm text-white/55 font-light leading-relaxed">
          Dona detectó oportunidades para tu negocio. Aquí preparamos
          borradores, planes y checklists.{" "}
          <span className="text-white/75">
            Nada se publica ni se envía sin tu aprobación.
          </span>
        </p>
      </div>

      {/* Botón generar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-xs text-white/35 font-light">
          {load.status === "ready"
            ? `${activas.length} acciones activas · ${historial.length} en historial`
            : "Cargando acciones…"}
        </p>
        <button
          onClick={handleGenerar}
          disabled={generando || load.status === "loading"}
          className="btn-secondary px-5 py-2.5 rounded-full text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
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
        <div className="glass-card rounded-2xl p-8 text-center">
          <p className="text-white/35 font-light">Cargando…</p>
        </div>
      )}

      {/* Error real (no empty state). El botón 'Generar acciones'
          sigue visible arriba · este panel solo informa la falla y
          ofrece reintento. */}
      {load.status === "error" && (
        <div className="glass-card rounded-2xl p-8 border-rose-500/15">
          <p className="text-white/70 font-light">
            No pudimos cargar tus acciones.
          </p>
          <p className="text-xs text-white/35 font-light mt-1 font-mono">
            {load.code}
          </p>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={fetchAcciones}
              className="btn-secondary px-5 py-2 rounded-full text-sm"
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
        <div className="glass-card rounded-2xl p-8">
          {perfilDiag ? (
            <>
              <p className="text-sm uppercase tracking-widest text-amber-300/80 font-light mb-3">
                {perfilDiag.estado === "missing"
                  ? "Diagnóstico pendiente"
                  : "Diagnóstico incompleto"}
              </p>
              <p className="text-white/70 font-light mb-2">
                {perfilDiag.razon}
              </p>
              {perfilDiag.estado === "incomplete" && (
                <p className="text-xs text-white/40 font-light mb-3 tabular-nums">
                  {perfilDiag.campos_llenos}/{perfilDiag.campos_totales} campos del diagnóstico llenos
                </p>
              )}
              <p className="text-sm text-white/55 font-light mb-4">
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
                  className="btn-secondary px-5 py-2.5 rounded-full text-sm disabled:opacity-50"
                >
                  Reintentar generar
                </button>
              </div>
            </>
          ) : (
            <div className="text-center">
              <p className="text-white/55 font-light mb-4">
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
            />
          ))}
        </div>
      )}

      {/* Historial */}
      {historial.length > 0 && (
        <details className="mt-8">
          <summary className="cursor-pointer text-xs text-white/35 font-light uppercase tracking-widest mb-3">
            Historial ({historial.length})
          </summary>
          <div className="space-y-3 mt-3">
            {historial.map((a) => (
              <CardAccion
                key={a.id}
                accion={a}
                enCurso={false}
                onAprobar={() => {}}
                onRechazar={() => {}}
                onEjecutar={() => {}}
              />
            ))}
          </div>
        </details>
      )}
    </section>
  );
}


interface CardAccionProps {
  accion: AccionAutomatizacion;
  enCurso: boolean;
  onAprobar: () => void;
  onRechazar: () => void;
  onEjecutar: () => void;
}

function CardAccion({
  accion,
  enCurso,
  onAprobar,
  onRechazar,
  onEjecutar,
}: CardAccionProps) {
  const r = accion.riesgo;
  const e = accion.estado;
  const result = safeParseJson(accion.result_json);
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
  const estadoLabelMostrado = highAprobadaPendienteConfirmacion
    ? "Aprobada · requiere confirmación dedicada"
    : ESTADO_LABEL[e];
  const estadoColorMostrado = highAprobadaPendienteConfirmacion
    ? "text-orange-300/90"
    : ESTADO_COLOR[e];
  const showAprobar =
    nextRequired === "approval_required" && r !== "critical";
  const showEjecutar = nextRequired === "execute_available";
  const showCriticalBlock = nextRequired === "reinforced_approval_required";
  const criticalBlockText = blockReason || COPY_CRITICAL_FALLBACK;
  const dedicatedBlockText = blockReason || COPY_HIGH_APROBADA_FALLBACK;

  return (
    <div className="glass-card rounded-2xl px-6 py-5">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base font-normal text-white">
              {accion.titulo}
            </span>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full border font-mono ${RIESGO_COLOR[r]}`}
            >
              {RIESGO_LABEL[r]}
            </span>
          </div>
          <p className="text-sm text-white/55 font-light leading-relaxed">
            {accion.descripcion}
          </p>
          {accion.razon_recomendacion && (
            <p className="text-xs text-white/35 font-light mt-2 italic">
              · {accion.razon_recomendacion}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span
            className={`text-xs font-light flex items-center gap-1.5 ${estadoColorMostrado}`}
          >
            {highAprobadaPendienteConfirmacion ? (
              <Lock className="w-3.5 h-3.5" />
            ) : (
              <IconoEstado estado={e} />
            )}
            {estadoLabelMostrado}
          </span>
          {accion.costo_creditos_estimado > 0 && (
            <span className="text-xs text-white/30 font-light tabular-nums">
              ~{accion.costo_creditos_estimado} créditos
            </span>
          )}
        </div>
      </div>

      {/* Aviso CRITICAL · texto preferentemente del backend
          (execution_block_reason); fallback a copy local si el payload
          es legacy. */}
      {showCriticalBlock && (
        <div className="mt-3 p-3 rounded-lg bg-rose-500/[0.06] border border-rose-500/20">
          <p className="text-xs text-rose-300/80 font-light flex items-start gap-2">
            <Lock className="w-4 h-4 mt-0.5 shrink-0" />
            {criticalBlockText}
          </p>
        </div>
      )}

      {/* Aviso HIGH aprobado · texto preferentemente del backend
          (execution_block_reason); fallback a copy local si el payload
          es legacy. */}
      {highAprobadaPendienteConfirmacion && (
        <div className="mt-3 p-3 rounded-lg bg-orange-500/[0.06] border border-orange-500/20">
          <p className="text-xs text-orange-300/80 font-light flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            {dedicatedBlockText}
          </p>
        </div>
      )}

      {/* Resultado dry-run */}
      {result && e === "completed" && (
        <div className="mt-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.06]">
          <p className="text-xs uppercase tracking-widest text-white/30 mb-2 font-light">
            Resultado
          </p>
          <pre className="text-xs text-white/60 font-mono whitespace-pre-wrap break-words leading-relaxed">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      {/* Error */}
      {accion.error_message && (e === "failed" || e === "rejected") && (
        <div className="mt-3 p-3 rounded-lg bg-rose-500/[0.04] border border-rose-500/15">
          <p className="text-xs text-rose-300/70 font-light">
            {accion.error_message}
          </p>
        </div>
      )}

      {/* Botones */}
      {!esTerminal(e) && (
        <div className="flex items-center justify-end gap-2 mt-4">
          {showAprobar && (
            <>
              <button
                onClick={onRechazar}
                disabled={enCurso}
                className="btn-secondary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                <XCircle className="w-3.5 h-3.5" />
                Rechazar
              </button>
              <button
                onClick={onAprobar}
                disabled={enCurso}
                className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
              >
                {enCurso ? (
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
              onClick={onEjecutar}
              disabled={enCurso}
              className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              {enCurso ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              Ejecutar (dry-run)
            </button>
          )}
          {highAprobadaPendienteConfirmacion && (
            <span
              aria-disabled="true"
              title="La confirmación dedicada con preview, costo y riesgo aún no está disponible desde este control. No habrá efecto externo hasta entonces."
              className="px-4 py-2 rounded-full text-xs flex items-center gap-1.5 bg-orange-500/[0.06] border border-orange-500/20 text-orange-300/80 font-light cursor-not-allowed select-none"
            >
              <Lock className="w-3.5 h-3.5" />
              Confirmación dedicada · próximamente
            </span>
          )}
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
