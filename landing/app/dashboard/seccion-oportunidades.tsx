"use client";

// landing/app/dashboard/seccion-oportunidades.tsx
// Oportunidades detectadas · el radar del negocio en el dashboard.
//
// Muestra las oportunidades que el Opportunity Engine detecta a partir
// del perfil y contexto del negocio, ANTES de convertirse en acciones.
// Es la primera superficie web del eslabón diagnóstico→oportunidad del
// core loop; el Action Center (sección siguiente) cubre acción→permiso→
// ejecución.
//
// Decisiones de UX:
//   - Solo lectura: detectar es gratis y sin efectos; convertir en
//     acciones sigue viviendo en el botón "Generar acciones" del
//     Action Center (una sola puerta de entrada al ciclo de permisos).
//   - Si el perfil está incompleto (perfil_estado !== "ready"), se
//     explica POR QUÉ no hay oportunidades y CUÁL es el siguiente paso,
//     con el mismo contrato perfil_* que usa el Action Center.
//   - Orden del backend (ya viene por prioridad) · no reordenamos.

import { useCallback, useEffect, useState } from "react";
import {
  Lightbulb,
  Loader2,
  RefreshCw,
  TrendingUp,
  ClipboardList,
} from "lucide-react";
import type {
  OportunidadDetectada,
  OportunidadesConEstadoResponse,
  NivelRiesgo,
} from "@/lib/automation-types";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: OportunidadesConEstadoResponse }
  | { status: "error"; code: string };

const IMPACTO_LABEL: Record<OportunidadDetectada["impacto_estimado"], string> = {
  alto: "Impacto alto",
  medio: "Impacto medio",
  bajo: "Impacto bajo",
};

const IMPACTO_COLOR: Record<OportunidadDetectada["impacto_estimado"], string> = {
  alto: "bg-emerald-600/10 text-emerald-700 border-emerald-600/40",
  medio: "bg-amber-500/15 text-amber-700 border-amber-500/40",
  bajo: "bg-[color:var(--bg-soft)] text-[color:var(--ink-2)] border-[color:var(--line)]",
};

const RIESGO_LABEL: Record<NivelRiesgo, string> = {
  low: "Riesgo bajo",
  medium: "Riesgo medio",
  high: "Riesgo alto",
  critical: "Riesgo crítico",
};

const RIESGO_COLOR: Record<NivelRiesgo, string> = {
  low: "bg-emerald-600/10 text-emerald-700 border-emerald-600/40",
  medium: "bg-amber-500/15 text-amber-700 border-amber-500/40",
  high: "bg-orange-500/10 text-orange-700 border-orange-500/40",
  critical: "bg-[#e64263]/10 text-[#e64263] border-[#e64263]/40",
};

export default function SeccionOportunidades() {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });

  const fetchOportunidades = useCallback(async () => {
    try {
      const res = await fetch("/api/automation/oportunidades", {
        cache: "no-store",
      });
      if (!res.ok) {
        setLoad({ status: "error", code: `error_${res.status}` });
        return;
      }
      const data = (await res.json()) as OportunidadesConEstadoResponse;
      setLoad({ status: "ready", data });
    } catch {
      setLoad({ status: "error", code: "network_error" });
    }
  }, []);

  useEffect(() => {
    setLoad({ status: "loading" });
    void fetchOportunidades();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const data = load.status === "ready" ? load.data : null;
  const oportunidades = data?.oportunidades ?? [];
  const perfilIncompleto =
    data?.perfil_estado !== undefined && data.perfil_estado !== "ready";

  return (
    <section>
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <Lightbulb className="w-4 h-4" />
        Oportunidades detectadas
      </h2>

      {/* Aviso UX general */}
      <div className="surface-card px-6 py-5 mb-4">
        <p className="text-sm text-[color:var(--ink-2)] leading-relaxed">
          El radar de Dona sobre tu negocio: qué conviene atacar ahora y
          por qué, a partir de tu diagnóstico y contexto.{" "}
          <span className="text-[color:var(--ink)] font-medium">
            Detectar no cuesta créditos ni ejecuta nada — para convertir
            una oportunidad en acción usa el Centro de acción.
          </span>
        </p>
      </div>

      {/* Contador + refrescar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-xs text-[color:var(--muted)]">
          {load.status === "ready"
            ? `${oportunidades.length} oportunidades detectadas`
            : "Cargando oportunidades…"}
        </p>
        <button
          onClick={fetchOportunidades}
          disabled={load.status === "loading"}
          className="btn-ghost px-5 py-2.5 rounded-full text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {load.status === "loading" ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Actualizar
        </button>
      </div>

      {/* Loading */}
      {load.status === "loading" && (
        <div className="surface-card p-8 text-center">
          <p className="text-[color:var(--muted)]">Cargando…</p>
        </div>
      )}

      {/* Error real */}
      {load.status === "error" && (
        <div className="surface-card p-8 border-[#e64263]/40">
          <p className="text-[color:var(--ink-2)]">
            No pudimos cargar tus oportunidades.
          </p>
          <p className="text-xs text-[color:var(--muted)] mt-1 font-mono">
            {load.code}
          </p>
          <button
            onClick={fetchOportunidades}
            className="btn-ghost px-5 py-2 rounded-full text-sm mt-3"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Perfil incompleto · explica por qué y qué sigue */}
      {load.status === "ready" && perfilIncompleto && (
        <div className="surface-card px-6 py-5 mb-4 border-amber-500/40">
          <p className="text-sm text-[color:var(--ink-2)]">
            {data?.perfil_razon ||
              "Tu diagnóstico de negocio está incompleto, por eso aún no vemos oportunidades."}
          </p>
          {typeof data?.perfil_campos_llenos === "number" &&
            typeof data?.perfil_campos_totales === "number" && (
              <p className="text-xs text-[color:var(--muted)] mt-2">
                Diagnóstico: {data.perfil_campos_llenos} de{" "}
                {data.perfil_campos_totales} campos completados
              </p>
            )}
          {data?.perfil_siguiente_paso && (
            <p className="text-xs text-amber-700 mt-2">
              {data.perfil_siguiente_paso}
            </p>
          )}
        </div>
      )}

      {/* Empty state (perfil listo pero sin oportunidades) */}
      {load.status === "ready" &&
        !perfilIncompleto &&
        oportunidades.length === 0 && (
          <div className="surface-card p-8 text-center">
            <p className="text-[color:var(--ink-2)]">
              No detectamos oportunidades nuevas por ahora.
            </p>
            <p className="text-xs text-[color:var(--muted)] mt-2">
              Dona vuelve a evaluar cuando cambia tu contexto de negocio.
            </p>
          </div>
        )}

      {/* Lista de oportunidades */}
      {load.status === "ready" && oportunidades.length > 0 && (
        <div className="space-y-4">
          {oportunidades.map((op) => (
            <TarjetaOportunidad key={op.id} oportunidad={op} />
          ))}
        </div>
      )}
    </section>
  );
}

function TarjetaOportunidad({
  oportunidad,
}: {
  oportunidad: OportunidadDetectada;
}) {
  const impacto = IMPACTO_LABEL[oportunidad.impacto_estimado]
    ? oportunidad.impacto_estimado
    : "medio";
  return (
    <article className="surface-card px-6 py-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <h3 className="text-[color:var(--ink)] font-semibold text-base flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[color:var(--muted)] shrink-0" />
          {oportunidad.titulo}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`text-[11px] px-2.5 py-1 rounded-full border font-medium ${IMPACTO_COLOR[impacto]}`}
          >
            {IMPACTO_LABEL[impacto]}
          </span>
          {RIESGO_LABEL[oportunidad.riesgo] && (
            <span
              className={`text-[11px] px-2.5 py-1 rounded-full border font-medium ${RIESGO_COLOR[oportunidad.riesgo]}`}
            >
              {RIESGO_LABEL[oportunidad.riesgo]}
            </span>
          )}
        </div>
      </div>

      <p className="text-sm text-[color:var(--ink-2)] leading-relaxed mt-3">
        {oportunidad.descripcion}
      </p>

      {oportunidad.razon && (
        <p className="text-xs text-[color:var(--muted)] mt-2">
          <span className="text-[color:var(--ink-2)]">Por qué ahora:</span>{" "}
          {oportunidad.razon}
        </p>
      )}

      <div className="flex items-center justify-between gap-3 mt-4 flex-wrap">
        {oportunidad.fuente_datos.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            {oportunidad.fuente_datos.map((fuente) => (
              <span
                key={fuente}
                className="text-[10px] px-2 py-0.5 rounded-full bg-[color:var(--bg-soft)] border border-[color:var(--line)] text-[color:var(--muted)]"
              >
                {fuente}
              </span>
            ))}
          </div>
        )}
        {oportunidad.playbook_sugerido && (
          <p className="text-[11px] text-[color:var(--muted)] flex items-center gap-1.5">
            <ClipboardList className="w-3.5 h-3.5" />
            Playbook sugerido:{" "}
            <span className="text-[color:var(--ink-2)]">
              {oportunidad.playbook_sugerido}
            </span>
          </p>
        )}
      </div>
    </article>
  );
}
