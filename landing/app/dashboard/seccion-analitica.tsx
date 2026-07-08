"use client";

// landing/app/dashboard/seccion-analitica.tsx — Analítica del negocio.
//
// Vista visual y agregada de TODO lo medible del usuario, al estilo del
// mockup aprobado del hero de la landing (barras, chips ±%, tarjeta de
// créditos con barra de gradiente):
//   - KPIs del período (ventas, gastos, utilidad, pedidos) con delta
//     semanal cuando el backend lo provee (/api/reportes mes + semana).
//   - Actividad de créditos: barras verticales de los últimos movimientos
//     (recargas en violeta, consumos en tinta suave) — datos de
//     dashboard-data que el shell ya tiene.
//   - Distribución de gastos por categoría (barras de gradiente).
//   - Resumen de acciones (activas vs históricas) con acceso directo.
//
// Solo lectura y solo datos reales: ninguna métrica se inventa. Cada
// bloque tiene su empty state si el usuario aún no registró nada.

import { useCallback, useEffect, useState } from "react";
import {
  LineChart,
  TrendingUp,
  TrendingDown,
  Wallet,
  Package,
  Zap,
  Loader2,
  RefreshCw,
  ArrowUpRight,
} from "lucide-react";
import type { Reporte, ReportesResponse } from "@/lib/reportes-types";
import type { UsuarioResumen } from "@/lib/dashboard-types";

// Espejo de esActiva/esTerminal de seccion-action-center.tsx.
const ESTADOS_ACCION_TERMINALES = ["completed", "rejected", "failed", "cancelled"];

type LoadReportes =
  | { status: "loading" }
  | { status: "ready"; mes: Reporte; semana: Reporte }
  | { status: "error"; code: string };

function formatMonto(n: number): string {
  return n.toLocaleString("es-MX", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export default function SeccionAnalitica({
  data,
  irAAcciones,
}: {
  data: UsuarioResumen;
  irAAcciones?: () => void;
}) {
  const [reportes, setReportes] = useState<LoadReportes>({ status: "loading" });
  const [acciones, setAcciones] = useState<{
    activas: number;
    historicas: number;
  } | null>(null);

  const fetchTodo = useCallback(async () => {
    setReportes({ status: "loading" });
    try {
      const [resMes, resSemana] = await Promise.all([
        fetch("/api/reportes?periodo=mes", { cache: "no-store" }),
        fetch("/api/reportes?periodo=semana", { cache: "no-store" }),
      ]);
      if (!resMes.ok || !resSemana.ok) {
        setReportes({
          status: "error",
          code: `error_${resMes.ok ? resSemana.status : resMes.status}`,
        });
        return;
      }
      const mes = ((await resMes.json()) as ReportesResponse).reporte;
      const semana = ((await resSemana.json()) as ReportesResponse).reporte;
      setReportes({ status: "ready", mes, semana });
    } catch {
      setReportes({ status: "error", code: "network_error" });
    }
  }, []);

  useEffect(() => {
    void fetchTodo();
    // Conteo de acciones (best-effort; el bloque se oculta si falla).
    let cancelado = false;
    (async () => {
      try {
        const res = await fetch("/api/automation/acciones", {
          cache: "no-store",
        });
        if (!res.ok || cancelado) return;
        const json = (await res.json()) as { acciones?: { estado: string }[] };
        if (!cancelado && Array.isArray(json.acciones)) {
          const historicas = json.acciones.filter((a) =>
            ESTADOS_ACCION_TERMINALES.includes(a.estado),
          ).length;
          setAcciones({
            activas: json.acciones.length - historicas,
            historicas,
          });
        }
      } catch {
        // opcional
      }
    })();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const mes = reportes.status === "ready" ? reportes.mes : null;
  const semana = reportes.status === "ready" ? reportes.semana : null;
  const delta = semana?.comparacion_semana_previa ?? null;

  // Actividad de créditos: últimos movimientos como barras verticales.
  const movimientos = data.transacciones_recientes.slice(0, 12);
  const maxAbs = Math.max(1, ...movimientos.map((t) => Math.abs(t.delta)));
  const consumido = movimientos
    .filter((t) => t.delta < 0)
    .reduce((s, t) => s + Math.abs(t.delta), 0);
  const recargado = movimientos
    .filter((t) => t.delta > 0)
    .reduce((s, t) => s + t.delta, 0);
  const saldo = data.creditos.saldo_actual;
  const pctSaldo =
    saldo + consumido > 0
      ? Math.round((saldo / (saldo + consumido)) * 100)
      : 100;

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <h2 className="eyebrow flex items-center gap-2">
          <LineChart className="w-4 h-4" />
          Analítica
        </h2>
        <button
          onClick={() => void fetchTodo()}
          disabled={reportes.status === "loading"}
          className="btn-ghost flex items-center gap-2 rounded-full px-5 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {reportes.status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Actualizar
        </button>
      </div>

      <div className="space-y-4">
        {/* ── KPIs del mes con delta semanal ── */}
        {reportes.status === "loading" && (
          <div className="surface-card p-8 text-center">
            <p className="text-[color:var(--muted)]">Cargando métricas…</p>
          </div>
        )}

        {reportes.status === "error" && (
          <div className="surface-card border-[#e64263]/40 p-8">
            <p className="text-[color:var(--ink-2)]">
              No pudimos cargar tus métricas de negocio.
            </p>
            <p className="mt-1 font-mono text-xs text-[color:var(--muted)]">
              {reportes.code}
            </p>
            <button
              onClick={() => void fetchTodo()}
              className="btn-ghost mt-3 rounded-full px-5 py-2 text-sm"
            >
              Reintentar
            </button>
          </div>
        )}

        {mes && (
          <>
            {mes.etiqueta && (
              <p className="text-xs text-[color:var(--muted)]">
                Período: {mes.etiqueta}
                {semana?.etiqueta ? ` · semana ${semana.etiqueta}` : ""}
              </p>
            )}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard
                label="Ventas"
                icono={TrendingUp}
                valor={`$${formatMonto(mes.ventas)}`}
                chip={
                  delta
                    ? {
                        texto: `${delta.delta_ventas_pct >= 0 ? "+" : ""}${delta.delta_ventas_pct.toFixed(1)}% sem.`,
                        positivo: delta.delta_ventas_pct >= 0,
                      }
                    : undefined
                }
              />
              <KpiCard
                label="Gastos"
                icono={TrendingDown}
                valor={`$${formatMonto(mes.gastos)}`}
              />
              <KpiCard
                label="Utilidad"
                icono={Wallet}
                valor={`$${formatMonto(mes.utilidad)}`}
                negativo={mes.utilidad < 0}
              />
              <KpiCard
                label="Pedidos"
                icono={Package}
                valor={String(mes.num_pedidos)}
                sub={
                  semana && semana.num_pedidos > 0
                    ? `${semana.pedidos_entregados ?? 0} entregados esta semana`
                    : undefined
                }
              />
            </div>
            {!mes.hay_datos && (
              <p className="text-xs text-[color:var(--muted)]">
                Aún no hay datos de negocio este período. Cuéntale a Dona tus
                ventas y gastos — &quot;vendí 3 pizzas en 450&quot; — y estas
                métricas cobran vida.
              </p>
            )}
          </>
        )}

        {/* ── Actividad de créditos + saldo ── */}
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <div className="surface-card p-6">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-semibold text-[color:var(--ink)]">
                Actividad de créditos
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--muted)]">
                Últimos movimientos
              </p>
            </div>
            {movimientos.length === 0 ? (
              <p className="py-10 text-center text-sm text-[color:var(--muted)]">
                Sin movimientos todavía — tu actividad aparecerá aquí.
              </p>
            ) : (
              <>
                <div className="mb-3 flex flex-wrap gap-2">
                  <span className="rounded-full bg-[color:var(--brand)] px-2.5 py-1 text-[11px] font-medium text-white">
                    Recargas +{recargado}
                  </span>
                  <span className="rounded-full bg-[color:var(--fill)] px-2.5 py-1 text-[11px] font-medium text-[color:var(--ink)]">
                    Consumo −{consumido}
                  </span>
                </div>
                <div className="flex h-32 items-end gap-[3px]">
                  {movimientos.map((t, i) => (
                    <span
                      key={i}
                      title={`${t.razon || "Movimiento"}: ${t.delta > 0 ? "+" : ""}${t.delta}`}
                      className="flex-1 rounded-full"
                      style={{
                        height: `${Math.max(8, Math.round((Math.abs(t.delta) / maxAbs) * 100))}%`,
                        background:
                          t.delta > 0
                            ? "rgba(91,91,240,0.85)"
                            : "rgba(11,11,18,0.12)",
                      }}
                    />
                  ))}
                </div>
                <div className="mt-3 border-t border-dashed border-[color:var(--line)] pt-2">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--muted)]">
                    Recargas en violeta · consumos en gris
                  </p>
                </div>
              </>
            )}
          </div>

          <div className="space-y-4">
            <div className="surface-fill p-5">
              <p className="text-[12.5px] text-[color:var(--ink-2)]">
                Créditos disponibles
              </p>
              <p className="mt-1 text-3xl font-medium tracking-tight text-[color:var(--ink)] tabular-nums">
                {saldo}
              </p>
              <div className="bar-track mt-4">
                <span className="bar-fill" style={{ width: `${pctSaldo}%` }} />
              </div>
              <p className="mt-2 text-[11.5px] text-[color:var(--muted)]">
                {consumido > 0
                  ? `${consumido} consumidos en tus últimos movimientos`
                  : "sin consumo reciente"}
              </p>
            </div>

            {acciones && (
              <div className="surface-card p-5">
                <div className="flex items-center gap-3">
                  <span className="surface-fill grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-xl font-medium text-[color:var(--brand-ink)]">
                    {String(acciones.activas).padStart(2, "0")}
                  </span>
                  <div>
                    <p className="text-[14px] font-semibold leading-tight text-[color:var(--ink)]">
                      Acciones activas
                    </p>
                    <p className="mt-0.5 text-xs text-[color:var(--muted)]">
                      {acciones.historicas} en historial
                    </p>
                  </div>
                </div>
                {irAAcciones && (
                  <button
                    type="button"
                    onClick={irAAcciones}
                    className="mt-4 inline-flex cursor-pointer items-center gap-2 rounded-full bg-[color:var(--fill)] px-4 py-2 text-[12px] font-medium text-[color:var(--ink)]"
                  >
                    <Zap className="h-3.5 w-3.5" />
                    Revisar acciones
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Distribución de gastos por categoría ── */}
        {mes && mes.top_categorias.length > 0 && (
          <div className="surface-card p-6">
            <p className="mb-4 text-sm font-semibold text-[color:var(--ink)]">
              Distribución de gastos
            </p>
            <ul className="space-y-4">
              {(() => {
                const maxCat = Math.max(
                  1,
                  ...mes.top_categorias.map((c) => c.total),
                );
                return mes.top_categorias.map((cat) => (
                  <li key={cat.categoria}>
                    <div className="mb-1.5 flex items-baseline justify-between gap-4">
                      <span className="truncate text-sm text-[color:var(--ink-2)]">
                        {cat.categoria}
                      </span>
                      <span className="shrink-0 text-sm font-medium tabular-nums text-[color:var(--ink)]">
                        ${formatMonto(cat.total)}
                      </span>
                    </div>
                    <div className="bar-track">
                      <span
                        className="bar-fill"
                        style={{
                          width: `${Math.max(4, Math.round((cat.total / maxCat) * 100))}%`,
                        }}
                      />
                    </div>
                  </li>
                ));
              })()}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

function KpiCard({
  label,
  icono: Icono,
  valor,
  chip,
  sub,
  negativo = false,
}: {
  label: string;
  icono: typeof TrendingUp;
  valor: string;
  chip?: { texto: string; positivo: boolean };
  sub?: string;
  negativo?: boolean;
}) {
  return (
    <div className="surface-card p-6">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="eyebrow flex items-center gap-2">
          <Icono className="h-4 w-4 text-[color:var(--muted)]" />
          {label}
        </p>
        {chip && (
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium text-white ${
              chip.positivo ? "bg-[color:var(--brand)]" : "bg-[#e64263]"
            }`}
          >
            {chip.texto}
          </span>
        )}
      </div>
      <p
        className={`text-3xl font-medium tabular-nums tracking-tight ${
          negativo ? "text-[color:var(--dato-neg)]" : "text-[color:var(--ink)]"
        }`}
      >
        {valor}
      </p>
      {sub && (
        <p className="mt-1.5 text-xs text-[color:var(--muted)]">{sub}</p>
      )}
    </div>
  );
}
