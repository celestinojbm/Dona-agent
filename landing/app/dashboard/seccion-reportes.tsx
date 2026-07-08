"use client";

// landing/app/dashboard/seccion-reportes.tsx
// Reportes / Medición · los números de negocio del usuario, visibles en web.
//
// Fase 1 (plataforma web): el usuario ve en el dashboard sus ventas, gastos,
// utilidad, pedidos y top categorías — los mismos números que hoy sólo obtiene
// por WhatsApp. Los datos vienen de /api/reportes → /internal/reportes
// (backend), que resuelve telefono desde la sesión y sólo agrega los datos de
// ese usuario.
//
// Decisiones de UX:
//   - Solo lectura: ver los números. Registrar ventas/gastos sigue viviendo
//     en el chat (WhatsApp); esta superficie no captura ni muta.
//   - Toggle mes / semana. Al cambiar, se recarga con el período elegido.
//   - Empty state con gracia: los datos dependen de captura por WhatsApp; si
//     el usuario aún no registró nada, el reporte nace vacío.

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Wallet,
  Package,
  Loader2,
  RefreshCw,
} from "lucide-react";
import type { PeriodoReporte, Reporte, ReportesResponse } from "@/lib/reportes-types";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; reporte: Reporte }
  | { status: "error"; code: string };

// Formatea un monto como moneda USD. El backend opera en créditos/moneda del
// negocio; aquí sólo damos formato legible con 2 decimales.
function formatMonto(n: number): string {
  return n.toLocaleString("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function SeccionReportes() {
  const [periodo, setPeriodo] = useState<PeriodoReporte>("mes");
  const [load, setLoad] = useState<LoadState>({ status: "loading" });

  const fetchReporte = useCallback(async (p: PeriodoReporte) => {
    setLoad({ status: "loading" });
    try {
      const res = await fetch(`/api/reportes?periodo=${p}`, {
        cache: "no-store",
      });
      if (!res.ok) {
        setLoad({ status: "error", code: `error_${res.status}` });
        return;
      }
      const data = (await res.json()) as ReportesResponse;
      setLoad({ status: "ready", reporte: data.reporte });
    } catch {
      setLoad({ status: "error", code: "network_error" });
    }
  }, []);

  useEffect(() => {
    void fetchReporte(periodo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [periodo]);

  const reporte = load.status === "ready" ? load.reporte : null;
  const comparacion = reporte?.comparacion_semana_previa ?? null;

  return (
    <section>
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Reportes
      </h2>

      {/* Aviso UX + toggle período */}
      <div className="surface-card px-6 py-5 mb-4">
        <p className="text-sm text-[color:var(--ink-2)] leading-relaxed">
          Tus números de negocio — ventas, gastos, utilidad y pedidos — que
          Dona registra desde tus mensajes, reunidos aquí para verlos de un
          vistazo.
        </p>
      </div>

      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div className="inline-flex rounded-full border border-[color:var(--line)] p-1 bg-white">
          {(["mes", "semana"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriodo(p)}
              disabled={load.status === "loading"}
              className={`px-5 py-1.5 rounded-full text-sm transition-colors disabled:cursor-not-allowed ${
                periodo === p
                  ? "pill-active font-medium"
                  : "text-[color:var(--muted)] hover:text-[color:var(--ink-2)]"
              }`}
            >
              {p === "mes" ? "Este mes" : "Esta semana"}
            </button>
          ))}
        </div>
        <button
          onClick={() => fetchReporte(periodo)}
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
            No pudimos cargar tus reportes.
          </p>
          <p className="text-xs text-[color:var(--muted)] mt-1 font-mono">
            {load.code}
          </p>
          <button
            onClick={() => fetchReporte(periodo)}
            className="btn-ghost px-5 py-2 rounded-full text-sm mt-3"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Empty state · los datos dependen de captura por WhatsApp */}
      {load.status === "ready" && reporte && !reporte.hay_datos && (
        <div className="surface-card p-8 text-center">
          <p className="text-[color:var(--ink-2)]">
            Aún no hay datos de negocio registrados
            {reporte.etiqueta ? ` en ${reporte.etiqueta}` : ""}.
          </p>
          <p className="text-xs text-[color:var(--muted)] mt-2">
            Cuéntale a Dona por WhatsApp tus ventas y gastos —
            &quot;vendí 3 pizzas en 450&quot;— y tus números aparecerán aquí.
          </p>
        </div>
      )}

      {/* Reporte con datos */}
      {load.status === "ready" && reporte && reporte.hay_datos && (
        <div className="space-y-4">
          {reporte.etiqueta && (
            <p className="text-xs text-[color:var(--muted)]">
              {reporte.etiqueta}
            </p>
          )}

          {/* Tarjetas de números clave */}
          <div className="grid sm:grid-cols-3 gap-4">
            <TarjetaMetrica
              label="Ventas"
              valor={reporte.ventas}
              icono={TrendingUp}
              acento="text-emerald-700"
            />
            <TarjetaMetrica
              label="Gastos"
              valor={reporte.gastos}
              icono={TrendingDown}
              acento="text-[color:var(--dato-neg)]"
            />
            <TarjetaMetrica
              label="Utilidad"
              valor={reporte.utilidad}
              icono={Wallet}
              acento={
                reporte.utilidad >= 0
                  ? "text-[color:var(--ink)]"
                  : "text-[color:var(--dato-neg)]"
              }
            />
          </div>

          {/* Pedidos + comparación */}
          <div className="surface-card px-6 py-5 flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <Package className="w-5 h-5 text-[color:var(--muted)]" />
              <div>
                <p className="text-sm text-[color:var(--ink-2)]">
                  {reporte.num_pedidos}{" "}
                  {reporte.num_pedidos === 1 ? "pedido" : "pedidos"}
                </p>
                {reporte.periodo === "semana" &&
                  reporte.num_pedidos > 0 && (
                    <p className="text-xs text-[color:var(--muted)] mt-0.5">
                      {reporte.pedidos_entregados ?? 0} entregados ·{" "}
                      {reporte.pedidos_pendientes ?? 0} en curso
                    </p>
                  )}
              </div>
            </div>
            {comparacion && (
              <div
                className={`text-sm font-medium flex items-center gap-1.5 ${
                  comparacion.delta_ventas_pct >= 0
                    ? "text-emerald-700"
                    : "text-[color:var(--dato-neg)]"
                }`}
              >
                {comparacion.delta_ventas_pct >= 0 ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )}
                {comparacion.delta_ventas_pct >= 0 ? "+" : ""}
                {comparacion.delta_ventas_pct.toFixed(1)}% vs. semana pasada
              </div>
            )}
          </div>

          {/* Top categorías de gasto */}
          {reporte.top_categorias.length > 0 && (
            <div className="surface-card overflow-hidden">
              <div className="px-6 py-4 border-b border-[color:var(--line)]">
                <p className="eyebrow">
                  Top categorías de gasto
                </p>
              </div>
              <ul className="divide-y divide-[color:var(--line)]">
                {reporte.top_categorias.map((cat) => (
                  <li
                    key={cat.categoria}
                    className="px-6 py-3.5 flex items-center justify-between gap-4"
                  >
                    <span className="text-sm text-[color:var(--ink-2)] truncate">
                      {cat.categoria}
                    </span>
                    <span className="text-sm text-[color:var(--ink)] font-medium tabular-nums shrink-0">
                      ${formatMonto(cat.total)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function TarjetaMetrica({
  label,
  valor,
  icono: Icono,
  acento,
}: {
  label: string;
  valor: number;
  icono: typeof TrendingUp;
  acento: string;
}) {
  return (
    <div className="surface-card p-6">
      <div className="flex items-center gap-2 mb-3">
        <Icono className={`w-4 h-4 ${acento}`} />
        <p className="eyebrow">
          {label}
        </p>
      </div>
      <p className="text-3xl font-medium tabular-nums tracking-tight text-[color:var(--ink)]">
        <span className="text-[color:var(--muted)] text-xl align-top">$</span>
        {formatMonto(valor)}
      </p>
    </div>
  );
}
