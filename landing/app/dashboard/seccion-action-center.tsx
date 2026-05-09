"use client";

// landing/app/dashboard/seccion-action-center.tsx — T2.1.B
// Action Center · sección del dashboard que muestra acciones recomendadas
// generadas por el Automation Core (T2.1.A). Permite generar, aprobar,
// rechazar y ejecutar (dry-run) acciones según su nivel de riesgo.
//
// Decisiones de UX:
//   - LOW se muestran como "Listas para ejecutar" · botón "Ejecutar".
//   - MEDIUM como "Esperan tu OK" · botones "Aprobar" / "Rechazar".
//   - HIGH como "Requieren aprobación explícita" · misma UI MEDIUM pero
//     con aviso adicional: aún tras aprobar, no hay ejecutor real
//     en T2.1.A/B.
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
  NivelRiesgo,
} from "@/lib/automation-types";

interface AccionesData {
  acciones: AccionAutomatizacion[];
  count: number;
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

  const fetchAcciones = useCallback(async () => {
    try {
      const res = await fetch("/api/automation/acciones", {
        cache: "no-store",
      });
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
      if (!res.ok) {
        alert("No pudimos generar acciones nuevas. Intenta de nuevo.");
      } else {
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

      {/* Error */}
      {load.status === "error" && (
        <div className="glass-card rounded-2xl p-8 border-rose-500/15">
          <p className="text-white/70 font-light">
            No pudimos cargar tus acciones.
          </p>
          <button
            onClick={fetchAcciones}
            className="btn-secondary mt-3 px-5 py-2 rounded-full text-sm"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Empty */}
      {load.status === "ready" && acciones.length === 0 && (
        <div className="glass-card rounded-2xl p-8 text-center">
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
  const showAprobar = e === "needs_approval" && r !== "critical";
  const showEjecutar =
    e === "approved" || (e === "pending" && r === "low");
  const showCriticalBlock = e === "needs_approval" && r === "critical";

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
            className={`text-xs font-light flex items-center gap-1.5 ${ESTADO_COLOR[e]}`}
          >
            <IconoEstado estado={e} />
            {ESTADO_LABEL[e]}
          </span>
          {accion.costo_creditos_estimado > 0 && (
            <span className="text-xs text-white/30 font-light tabular-nums">
              ~{accion.costo_creditos_estimado} créditos
            </span>
          )}
        </div>
      </div>

      {/* Aviso CRITICAL */}
      {showCriticalBlock && (
        <div className="mt-3 p-3 rounded-lg bg-rose-500/[0.06] border border-rose-500/20">
          <p className="text-xs text-rose-300/80 font-light flex items-start gap-2">
            <Lock className="w-4 h-4 mt-0.5 shrink-0" />
            Esta acción es crítica. Requiere confirmación reforzada y
            aún no puede ejecutarse automáticamente.
          </p>
        </div>
      )}

      {/* Aviso HIGH aprobado */}
      {e === "approved" && r === "high" && (
        <div className="mt-3 p-3 rounded-lg bg-orange-500/[0.06] border border-orange-500/20">
          <p className="text-xs text-orange-300/80 font-light flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            Esta acción es de alto impacto. Está aprobada pero todavía
            requiere ejecutor con guardrails reforzados (próximo PR).
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
