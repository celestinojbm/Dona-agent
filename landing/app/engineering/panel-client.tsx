"use client";

// landing/app/engineering/panel-client.tsx
// UI del panel de ingeniería v2. Hace polling a /api/engineering/data cada
// 60s y renderiza un dashboard completo: sidebar con activity feed y ramas,
// fila de KPIs con sparklines, gráfico de área de commits diarios, barras
// semanales y por día, donut de lenguajes, pipelines de CI, build log del
// último run, deploys de Render con histórico, roadmap y commit history.
//
// Estética: dark editorial (headers en MAYÚSCULAS con tracking, números en
// mono, glass cards) — misma familia visual del resto del landing.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  CIRun,
  CommitInfo,
  DeploysServicio,
  PanelData,
  PRInfo,
  Roadmap,
} from "@/lib/panel-types";
import {
  AnilloPct,
  AreaChart,
  BarraProgreso,
  BarrasV,
  Donut,
  PALETA,
  Sparkline,
} from "./panel-charts";

const POLL_MS = 60_000;

// ── Helpers de formato ─────────────────────────────────────────────────────

function haceCuanto(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `hace ${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `hace ${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `hace ${h}h`;
  return `hace ${Math.floor(h / 24)}d`;
}

function duracionLegible(seg: number | null | undefined): string {
  if (seg === null || seg === undefined || seg < 0) return "—";
  if (seg < 60) return `${seg}s`;
  const m = Math.floor(seg / 60);
  return `${m}m ${seg % 60}s`;
}

function numero(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("es");
}

function iniciales(nombre: string): string {
  return nombre
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// ── Datos derivados ────────────────────────────────────────────────────────

type Tono = "ok" | "error" | "curso" | "neutro";

function tonoRun(run: CIRun): Tono {
  if (run.estado !== "completed") return "curso";
  if (run.conclusion === "success") return "ok";
  if (run.conclusion === "failure") return "error";
  return "neutro";
}

function tonoDeployEstado(estado: string | undefined): Tono {
  if (!estado) return "neutro";
  if (estado === "live") return "ok";
  if (estado.includes("fail")) return "error";
  if (
    estado.includes("progress") ||
    estado === "created" ||
    estado === "queued"
  )
    return "curso";
  return "neutro";
}

/**
 * Success rate + duraciones (viejo→nuevo) de los runs de CI.
 * Solo cuentan runs con veredicto real (success/failure): un run cancelado
 * por concurrency al pushear varias veces seguidas no es un fallo de tests
 * y no debe bajar el anillo. El rótulo usa el mismo denominador.
 */
function ciStats(ci: CIRun[] | null) {
  if (!ci || ci.length === 0) {
    return {
      exitoPct: null as number | null,
      duraciones: [] as number[],
      totalConsiderados: 0,
    };
  }
  const relevantes = ci.filter(
    (r) =>
      r.estado === "completed" &&
      (r.conclusion === "success" || r.conclusion === "failure"),
  );
  const exitoPct =
    relevantes.length > 0
      ? (relevantes.filter((r) => r.conclusion === "success").length /
          relevantes.length) *
        100
      : null;
  // Sparkline con la suite principal (la más lenta e informativa).
  const suite = relevantes.filter(
    (r) =>
      (r.nombre.toLowerCase().includes("pytest") ||
        r.nombre.toLowerCase().includes("test")) &&
      r.duracion_segundos !== null,
  );
  const fuente = suite.length >= 2 ? suite : relevantes;
  const duraciones = fuente
    .map((r) => r.duracion_segundos)
    .filter((s): s is number => s !== null)
    .reverse();
  return { exitoPct, duraciones, totalConsiderados: relevantes.length };
}

type EventoFeed = {
  clave: string;
  tipo: "commit" | "pr_merged" | "pr_abierto" | "deploy";
  texto: string;
  fecha: string;
  color: string;
};

/** Mezcla commits, PRs y deploys en un feed cronológico para el sidebar. */
function feedActividad(data: PanelData | null): EventoFeed[] {
  if (!data) return [];
  const eventos: EventoFeed[] = [];
  for (const c of data.commits?.slice(0, 6) ?? []) {
    eventos.push({
      clave: `c-${c.sha_corto}`,
      tipo: "commit",
      texto: c.mensaje,
      fecha: c.fecha,
      color: "#7C3AED",
    });
  }
  for (const p of data.prs_merged?.slice(0, 4) ?? []) {
    eventos.push({
      clave: `pm-${p.numero}`,
      tipo: "pr_merged",
      texto: `PR #${p.numero} mergeado · ${p.titulo}`,
      fecha: p.mergeado_en ?? p.creado_en,
      color: "#34d399",
    });
  }
  for (const p of data.prs_abiertos?.slice(0, 3) ?? []) {
    eventos.push({
      clave: `pa-${p.numero}`,
      tipo: "pr_abierto",
      texto: `PR #${p.numero} abierto · ${p.titulo}`,
      fecha: p.creado_en,
      color: "#fbbf24",
    });
  }
  for (const [nombre, srv] of [
    ["web", data.deploys?.web],
    ["worker", data.deploys?.worker],
  ] as const) {
    if (srv?.actual) {
      eventos.push({
        clave: `d-${nombre}`,
        tipo: "deploy",
        texto: `Deploy ${nombre} ${srv.actual.estado} · ${srv.actual.commit_corto}`,
        fecha: srv.actual.creado_en,
        color: "#38bdf8",
      });
    }
  }
  return eventos
    .filter((e) => e.fecha)
    .sort((a, b) => Date.parse(b.fecha) - Date.parse(a.fecha))
    .slice(0, 8);
}

// ── Piezas visuales chicas ─────────────────────────────────────────────────

function TituloCard({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-mono text-[11px] tracking-[0.25em] uppercase text-white/40 mb-5">
      {children}
    </h2>
  );
}

function Card({
  children,
  className = "",
  compacta = false,
}: {
  children: React.ReactNode;
  className?: string;
  /** Padding reducido (KPIs). */
  compacta?: boolean;
}) {
  return (
    <section
      className={`glass-card rounded-2xl ${compacta ? "px-5 py-4" : "p-6"} ${className}`}
    >
      {children}
    </section>
  );
}

function Punto({ tono }: { tono: Tono }) {
  const color =
    tono === "ok"
      ? "bg-emerald-400"
      : tono === "error"
        ? "bg-red-400"
        : tono === "curso"
          ? "bg-amber-400 animate-pulse"
          : "bg-white/30";
  return (
    <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${color}`} />
  );
}

function PillEstado({ run }: { run: CIRun }) {
  const t = tonoRun(run);
  const estilos: Record<Tono, string> = {
    ok: "bg-emerald-400/10 text-emerald-300 border-emerald-400/20",
    error: "bg-red-400/10 text-red-300 border-red-400/20",
    curso: "bg-amber-400/10 text-amber-300 border-amber-400/20",
    neutro: "bg-white/5 text-white/50 border-white/10",
  };
  const texto =
    run.estado !== "completed"
      ? "RUNNING"
      : (run.conclusion ?? "?").toUpperCase();
  return (
    <span
      className={`font-mono text-[10px] tracking-wider px-2 py-0.5 rounded border ${estilos[t]}`}
    >
      {texto}
    </span>
  );
}

function Stat({
  etiqueta,
  valor,
  sub,
}: {
  etiqueta: string;
  valor: string;
  sub?: string;
}) {
  return (
    <div>
      <p className="font-mono text-3xl font-extralight text-gradient-stat">
        {valor}
      </p>
      <p className="text-xs text-white/40 mt-1 uppercase tracking-wider">
        {etiqueta}
      </p>
      {sub && <p className="font-mono text-[10px] text-white/50 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────

function Sidebar({
  data,
  onSalir,
}: {
  data: PanelData | null;
  onSalir: () => void;
}) {
  const feed = useMemo(() => feedActividad(data), [data]);
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-white/[0.06] bg-black/40 backdrop-blur-md px-5 py-8 sticky top-0 h-screen overflow-y-auto">
      <div className="mb-8">
        <p className="font-mono text-xs tracking-[0.3em] text-white/40 uppercase">
          Dona
        </p>
        <p className="text-sm font-light uppercase tracking-widest mt-1 text-white/90">
          Engineering
          <br />
          Control Center
        </p>
      </div>

      <p className="font-mono text-[10px] tracking-[0.25em] uppercase text-white/35 mb-3">
        Activity feed
      </p>
      <ul className="space-y-3 mb-8">
        {feed.length === 0 && (
          <li className="text-xs text-white/30">cargando…</li>
        )}
        {feed.map((e) => (
          <li key={e.clave} className="flex gap-2.5 text-xs leading-snug">
            <span
              className="mt-1 inline-block w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: e.color }}
            />
            <span className="min-w-0">
              <span className="text-white/65 line-clamp-2">{e.texto}</span>
              <span className="font-mono text-[10px] text-white/50">
                {haceCuanto(e.fecha)}
              </span>
            </span>
          </li>
        ))}
      </ul>

      <p className="font-mono text-[10px] tracking-[0.25em] uppercase text-white/35 mb-3">
        Ramas · {numero(data?.repo?.ramas)}
      </p>
      <ul className="space-y-1.5 mb-8">
        {(data?.repo?.nombres_ramas ?? []).slice(0, 8).map((r) => (
          <li
            key={r}
            className="font-mono text-[11px] text-white/50 truncate flex items-center gap-2"
          >
            <span
              className={`inline-block w-1 h-1 rounded-full ${r === "main" ? "bg-emerald-400" : "bg-white/25"}`}
            />
            {r}
          </li>
        ))}
      </ul>

      <div className="mt-auto pt-6">
        <button
          onClick={onSalir}
          className="btn-secondary w-full rounded-md px-3 py-2 text-[11px] uppercase tracking-widest"
        >
          Salir
        </button>
      </div>
    </aside>
  );
}

// ── Cards ──────────────────────────────────────────────────────────────────

function CardRepo({ data }: { data: PanelData | null }) {
  return (
    <Card>
      <TituloCard>Repository Analytics</TituloCard>
      <div className="grid grid-cols-2 gap-6">
        <Stat etiqueta="Commits" valor={numero(data?.repo?.total_commits)} />
        <Stat
          etiqueta="PRs abiertos"
          valor={numero(data?.repo?.prs_abiertos)}
        />
        <Stat
          etiqueta="Issues abiertos"
          valor={numero(data?.repo?.issues_abiertos)}
        />
        <Stat etiqueta="Ramas" valor={numero(data?.repo?.ramas)} />
      </div>
    </Card>
  );
}

function CardVelocity({ data }: { data: PanelData | null }) {
  const diaria = data?.velocity_diaria ?? null;
  const semanal = data?.velocity ?? null;
  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <TituloCard>Commit velocity · 30 días</TituloCard>
        {diaria && (
          <span className="font-mono text-[10px] text-white/50">
            máx {Math.max(...diaria.map((p) => p.commits))}/día
          </span>
        )}
      </div>
      {diaria && diaria.length >= 2 ? (
        <>
          <AreaChart
            valores={diaria.map((p) => p.commits)}
            etiquetas={diaria.map((p) => p.fecha)}
            alto={170}
          />
          <div className="flex justify-between font-mono text-[10px] text-white/50 mt-1">
            <span>{diaria[0].fecha}</span>
            <span>{diaria[diaria.length - 1].fecha}</span>
          </div>
        </>
      ) : (
        <p className="text-sm text-white/35 h-[170px] flex items-center">
          Sin datos (GitHub computando estadísticas)
        </p>
      )}
      {semanal && semanal.length > 0 && (
        <div className="mt-5 pt-4 border-t border-white/[0.05]">
          <p className="font-mono text-[10px] tracking-[0.2em] uppercase text-white/30 mb-2">
            Por semana · 12 semanas
          </p>
          <BarrasV valores={semanal} alto={64} resaltarUltima />
        </div>
      )}
    </Card>
  );
}

const DIAS_SEMANA = ["L", "M", "X", "J", "V", "S", "D"];

function CardActividad({ data }: { data: PanelData | null }) {
  const act = data?.actividad_semanal ?? null;
  const maxIdx = act ? act.indexOf(Math.max(...act)) : -1;
  return (
    <Card>
      <TituloCard>Actividad por día · último año</TituloCard>
      {act ? (
        <>
          <BarrasV valores={act} etiquetas={DIAS_SEMANA} alto={150} />
          <p className="font-mono text-[10px] text-white/50 mt-3">
            día más activo:{" "}
            {maxIdx >= 0
              ? ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][maxIdx]
              : "—"}
          </p>
        </>
      ) : (
        <p className="text-sm text-white/35">Sin datos</p>
      )}
    </Card>
  );
}

function CardCI({ data }: { data: PanelData | null }) {
  const runs = data?.ci ?? null;
  return (
    <Card>
      <TituloCard>CI/CD Pipelines · GitHub Actions</TituloCard>
      {runs && runs.length ? (
        <ul className="space-y-3">
          {runs.slice(0, 7).map((r) => (
            <li key={r.id} className="flex items-center gap-3 text-sm">
              <Punto tono={tonoRun(r)} />
              <a
                href={r.url}
                target="_blank"
                rel="noreferrer"
                className="truncate hover:text-white text-white/70 transition-colors"
              >
                {r.nombre}
              </a>
              <span className="font-mono text-xs text-white/55 truncate max-w-[9rem] hidden sm:inline">
                {r.rama}
              </span>
              <span className="ml-auto shrink-0 flex items-center gap-2">
                <span className="font-mono text-[10px] text-white/50 hidden sm:inline">
                  {duracionLegible(r.duracion_segundos)} ·{" "}
                  {haceCuanto(r.iniciado_en)}
                </span>
                <PillEstado run={r} />
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-white/35">Sin runs</p>
      )}
    </Card>
  );
}

function CardBuildLog({ data }: { data: PanelData | null }) {
  const pasos = data?.ci_pasos ?? null;
  const run = data?.ci?.[0] ?? null;
  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <TituloCard>Build log · último run</TituloCard>
        {run && (
          <a
            href={run.url}
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[10px] text-white/50 hover:text-white transition-colors"
          >
            {run.nombre} · {run.rama}
          </a>
        )}
      </div>
      <div className="rounded-lg bg-black/50 border border-white/[0.06] p-4 font-mono text-[11px] leading-relaxed max-h-56 overflow-y-auto">
        {pasos && pasos.length ? (
          pasos.map((p, i) => {
            const hora = p.iniciado_en
              ? new Date(p.iniciado_en).toLocaleTimeString("es", {
                  hour12: false,
                })
              : "--:--:--";
            const okStep = p.conclusion === "success";
            const skip = p.conclusion === "skipped";
            return (
              <div key={i} className="flex gap-2 whitespace-nowrap">
                <span className="text-white/50 shrink-0">{hora}</span>
                <span
                  className={
                    okStep
                      ? "text-emerald-400"
                      : skip
                        ? "text-white/30"
                        : p.conclusion
                          ? "text-red-400"
                          : "text-amber-300"
                  }
                >
                  {okStep ? "✓" : skip ? "○" : p.conclusion ? "✗" : "›"}
                </span>
                <span className="text-white/70 truncate">{p.nombre}</span>
                <span className="text-white/50 ml-auto shrink-0">
                  {duracionLegible(p.duracion_segundos)}
                </span>
              </div>
            );
          })
        ) : (
          <span className="text-white/50">sin steps disponibles</span>
        )}
      </div>
    </Card>
  );
}

function FilaServicio({
  nombre,
  srv,
}: {
  nombre: string;
  srv: DeploysServicio | null;
}) {
  const actual = srv?.actual ?? null;
  const prom =
    srv && srv.duraciones.length
      ? Math.round(
          srv.duraciones.reduce((a, b) => a + b, 0) / srv.duraciones.length,
        )
      : null;
  return (
    <div className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-center gap-3 text-sm">
        <Punto tono={tonoDeployEstado(actual?.estado)} />
        <span className="uppercase tracking-wider text-xs text-white/60 w-14 shrink-0">
          {nombre}
        </span>
        {actual ? (
          <>
            <span className="font-mono text-xs text-white/80">
              {actual.estado}
            </span>
            <span className="font-mono text-xs text-white/55 truncate">
              {actual.commit_corto}
            </span>
            <span className="font-mono text-[10px] text-white/50 ml-auto shrink-0">
              {haceCuanto(actual.creado_en)}
            </span>
          </>
        ) : (
          <span className="text-xs text-white/35">sin datos</span>
        )}
      </div>
      {srv && srv.duraciones.length >= 2 && (
        <div className="flex items-center gap-3 mt-2 pl-5">
          <Sparkline valores={srv.duraciones} color="#38bdf8" />
          <span className="font-mono text-[10px] text-white/50">
            deploy prom {duracionLegible(prom)} · últimos{" "}
            {srv.duraciones.length}
          </span>
        </div>
      )}
    </div>
  );
}

function CardDeploys({ data }: { data: PanelData | null }) {
  return (
    <Card>
      <TituloCard>Deploys · Render</TituloCard>
      <div className="divide-y divide-white/[0.05]">
        <FilaServicio nombre="Web" srv={data?.deploys?.web ?? null} />
        <FilaServicio nombre="Worker" srv={data?.deploys?.worker ?? null} />
      </div>
    </Card>
  );
}

function CardLenguajes({ data }: { data: PanelData | null }) {
  const lenguajes = data?.lenguajes ?? null;
  return (
    <Card>
      <TituloCard>Lenguajes del repo</TituloCard>
      {lenguajes && lenguajes.length ? (
        <div className="flex items-center gap-6">
          <Donut
            partes={lenguajes.map((l) => ({
              nombre: l.nombre,
              valor: l.porcentaje,
            }))}
          />
          <ul className="space-y-2 min-w-0">
            {lenguajes.map((l, i) => (
              <li key={l.nombre} className="flex items-center gap-2 text-xs">
                <span
                  className="inline-block w-2 h-2 rounded-sm shrink-0"
                  style={{ background: PALETA[i % PALETA.length] }}
                />
                <span className="text-white/65 truncate">{l.nombre}</span>
                <span className="font-mono text-white/55 ml-auto">
                  {l.porcentaje}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-white/35">Sin datos</p>
      )}
    </Card>
  );
}

function CardRoadmap({ roadmap }: { roadmap: Roadmap }) {
  const pctPorEstado: Record<string, number> = {
    hecho: 100,
    en_curso: 60,
    siguiente: 12,
    pendiente: 0,
  };
  const colorPorEstado: Record<string, string> = {
    hecho: "#34d399",
    en_curso: "#7C3AED",
    siguiente: "#2563EB",
    pendiente: "#475569",
  };
  const hechos = roadmap.items.filter((i) => i.estado === "hecho").length;
  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <TituloCard>{roadmap.titulo}</TituloCard>
        <span className="font-mono text-[10px] text-white/50">
          {hechos}/{roadmap.items.length} · act. {roadmap.actualizado}
        </span>
      </div>
      <ul className="space-y-3.5">
        {roadmap.items.map((item) => (
          <li key={item.id}>
            <div className="flex items-center gap-3 text-sm mb-1.5">
              <span className="font-mono text-[10px] text-white/50 w-12 shrink-0">
                {item.id}
              </span>
              <span
                className={`truncate text-[13px] ${item.estado === "hecho" ? "text-white/40" : "text-white/80"}`}
              >
                {item.nombre}
              </span>
              {item.detalle && (
                <span className="font-mono text-[10px] text-white/50 ml-auto shrink-0 hidden sm:inline">
                  {item.detalle}
                </span>
              )}
            </div>
            <div className="pl-[60px]">
              <BarraProgreso
                pct={pctPorEstado[item.estado] ?? 0}
                color={colorPorEstado[item.estado] ?? "#475569"}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function FilaPR({ pr }: { pr: PRInfo }) {
  return (
    <li className="flex items-center gap-3 text-sm">
      <Punto tono={pr.mergeado_en ? "ok" : pr.draft ? "neutro" : "curso"} />
      <span className="font-mono text-xs text-white/55 shrink-0">
        #{pr.numero}
      </span>
      <a
        href={pr.url}
        target="_blank"
        rel="noreferrer"
        className="truncate text-white/70 hover:text-white transition-colors"
      >
        {pr.titulo}
      </a>
      <span className="font-mono text-[10px] text-white/50 ml-auto shrink-0">
        {haceCuanto(pr.mergeado_en ?? pr.creado_en)}
      </span>
    </li>
  );
}

function CardPRs({ data }: { data: PanelData | null }) {
  const abiertos = data?.prs_abiertos ?? null;
  const merged = data?.prs_merged ?? null;
  // Conteo exacto desde la Search API (el bridge lo calcula server-side);
  // contar sobre la lista visual (capada a 8) daba un techo artificial.
  const merged7d = data?.prs_merged_7d ?? null;
  return (
    <Card>
      <TituloCard>Issues & PRs</TituloCard>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Stat etiqueta="Abiertos" valor={numero(abiertos?.length)} />
        <Stat etiqueta="Merged 7d" valor={numero(merged7d)} />
        <Stat
          etiqueta="Issues"
          valor={numero(data?.repo?.issues_abiertos)}
        />
      </div>
      {abiertos && abiertos.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-[0.2em] text-white/35 mb-2.5">
            Abiertos
          </p>
          <ul className="space-y-2.5 mb-5">
            {abiertos.slice(0, 4).map((pr) => (
              <FilaPR key={pr.numero} pr={pr} />
            ))}
          </ul>
        </>
      )}
      <p className="text-[10px] uppercase tracking-[0.2em] text-white/35 mb-2.5">
        Mergeados recientes
      </p>
      {merged && merged.length ? (
        <ul className="space-y-2.5">
          {merged.slice(0, 4).map((pr) => (
            <FilaPR key={pr.numero} pr={pr} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-white/35">Ninguno</p>
      )}
    </Card>
  );
}

function CardCommits({ commits }: { commits: CommitInfo[] | null }) {
  return (
    <Card>
      <TituloCard>Commit history · main</TituloCard>
      {commits && commits.length ? (
        <ul className="space-y-3">
          {commits.slice(0, 9).map((c) => (
            <li key={c.sha_corto} className="flex items-center gap-3 text-sm">
              <span
                className="w-7 h-7 rounded-full bg-gradient-to-br from-[#7C3AED]/40 to-[#2563EB]/40 border border-white/10 flex items-center justify-center font-mono text-[10px] text-white/70 shrink-0"
                title={c.autor}
              >
                {iniciales(c.autor)}
              </span>
              <span className="truncate text-white/70">{c.mensaje}</span>
              <a
                href={c.url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-[10px] text-[#a78bfa] hover:text-white transition-colors ml-auto shrink-0"
              >
                {c.sha_corto}
              </a>
              <span className="font-mono text-[10px] text-white/50 shrink-0 w-16 text-right">
                {haceCuanto(c.fecha)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-white/35">Sin datos</p>
      )}
    </Card>
  );
}

function CardCodeHealth({ data }: { data: PanelData | null }) {
  const suite = data?.ci?.find(
    (r) =>
      r.rama === "main" &&
      r.estado === "completed" &&
      (r.nombre.toLowerCase().includes("pytest") ||
        r.nombre.toLowerCase().includes("test")),
  );
  return (
    <Card>
      <TituloCard>Code Health</TituloCard>
      <div className="grid grid-cols-3 gap-4">
        <Stat
          etiqueta="Suite main"
          valor={suite ? (suite.conclusion === "success" ? "✓" : "✗") : "—"}
          sub={suite ? duracionLegible(suite.duracion_segundos) : undefined}
        />
        <Stat etiqueta="Coverage" valor="—" sub="v2 · desde CI" />
        <Stat etiqueta="Tech debt" valor="—" sub="v2 · por definir" />
      </div>
      <p className="text-[10px] text-white/30 mt-4 font-mono">
        sin métricas inventadas: lo que no se mide todavía, va con “—”
      </p>
    </Card>
  );
}

// ── Panel ──────────────────────────────────────────────────────────────────

export default function PanelClient({ roadmap }: { roadmap: Roadmap }) {
  const router = useRouter();
  const [data, setData] = useState<PanelData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actualizado, setActualizado] = useState<Date | null>(null);
  const cargando = useRef(false);

  const cargar = useCallback(async () => {
    if (cargando.current) return;
    cargando.current = true;
    try {
      const res = await fetch("/api/engineering/data", { cache: "no-store" });
      if (res.status === 401) {
        // Cookie expirada/inválida → volver al gate.
        router.refresh();
        return;
      }
      if (!res.ok) {
        setError(`Error ${res.status} consultando datos`);
        return;
      }
      const json = (await res.json()) as PanelData;
      setData(json);
      setActualizado(new Date());
      setError(null);
    } catch {
      setError("No se pudo conectar con el panel");
    } finally {
      cargando.current = false;
    }
  }, [router]);

  useEffect(() => {
    cargar();
    const id = setInterval(cargar, POLL_MS);
    return () => clearInterval(id);
  }, [cargar]);

  async function salir() {
    await fetch("/api/engineering/login", { method: "DELETE" });
    router.refresh();
  }

  const {
    exitoPct,
    duraciones: duracionesCI,
    totalConsiderados,
  } = useMemo(() => ciStats(data?.ci ?? null), [data]);
  const mergeHoras = data?.merge_horas_prom ?? null;
  const deployWeb = data?.deploys?.web ?? null;
  const deployProm =
    deployWeb && deployWeb.duraciones.length
      ? Math.round(
          deployWeb.duraciones.reduce((a, b) => a + b, 0) /
            deployWeb.duraciones.length,
        )
      : null;
  const commitsSemana = data?.velocity?.[data.velocity.length - 1] ?? null;
  const semanaAnterior = data?.velocity?.[data.velocity.length - 2] ?? null;
  const deltaSemana =
    commitsSemana !== null && semanaAnterior !== null && semanaAnterior > 0
      ? Math.round(((commitsSemana - semanaAnterior) / semanaAnterior) * 100)
      : null;

  return (
    <div className="legacy-shell flex">
      <Sidebar data={data} onSalir={salir} />

      <main className="flex-1 min-w-0 px-4 sm:px-8 py-8 max-w-[1480px] mx-auto">
        {/* Header */}
        <header className="flex flex-wrap items-baseline gap-4 mb-8">
          <div>
            <p className="font-mono text-xs tracking-[0.3em] text-white/40 uppercase">
              Dona Engineering /
            </p>
            <h1 className="text-3xl font-extralight tracking-wide uppercase mt-1">
              Progreso en tiempo real
            </h1>
          </div>
          <div className="ml-auto flex items-center gap-3 text-xs font-mono text-white/40">
            {error ? (
              <span className="text-red-400">{error}</span>
            ) : (
              <span>
                {actualizado
                  ? // Hora absoluta: el "hace Xs" relativo solo se re-renderiza
                    // con cada poll, así que quedaba congelado en "hace 0s".
                    `sync ${actualizado.toLocaleTimeString("es", { hour12: false })} · poll 60s`
                  : "cargando…"}
              </span>
            )}
            <button
              onClick={cargar}
              className="btn-secondary rounded-md px-3 py-1.5 uppercase tracking-wider"
            >
              Refrescar
            </button>
            <button
              onClick={salir}
              className="btn-secondary rounded-md px-3 py-1.5 uppercase tracking-wider lg:hidden"
            >
              Salir
            </button>
          </div>
        </header>

        {/* Errores parciales de secciones */}
        {data && data.errores.length > 0 && (
          <p className="mb-6 text-xs font-mono text-amber-400/80">
            Secciones sin datos: {data.errores.join(" · ")}
          </p>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-5">
          <Card compacta className="flex items-center gap-4">
            <AnilloPct pct={exitoPct} etiqueta="CI success" />
            <div>
              <p className="text-[10px] uppercase tracking-[0.2em] text-white/40">
                CI success
              </p>
              <p className="font-mono text-[10px] text-white/50 mt-1">
                {totalConsiderados} runs con veredicto
              </p>
              {duracionesCI.length >= 2 && (
                <Sparkline valores={duracionesCI} color="#34d399" ancho={90} />
              )}
            </div>
          </Card>
          <Card compacta>
            <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-1">
              Deploy time
            </p>
            <p className="font-mono text-2xl font-extralight text-gradient-stat">
              {duracionLegible(deployProm)}
            </p>
            {deployWeb && deployWeb.duraciones.length >= 2 && (
              <Sparkline valores={deployWeb.duraciones} color="#38bdf8" />
            )}
          </Card>
          <Card compacta>
            <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-1">
              Merge velocity
            </p>
            <p className="font-mono text-2xl font-extralight text-gradient-stat">
              {mergeHoras === null ? "—" : `${mergeHoras.toFixed(1)}h`}
            </p>
            <p className="font-mono text-[10px] text-white/50 mt-1">
              apertura → merge (prom)
            </p>
          </Card>
          <Card compacta>
            <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-1">
              Commits semana
            </p>
            <p className="font-mono text-2xl font-extralight text-gradient-stat">
              {numero(commitsSemana)}
            </p>
            {deltaSemana !== null && (
              <p
                className={`font-mono text-[10px] mt-1 ${deltaSemana >= 0 ? "text-emerald-400/80" : "text-red-400/80"}`}
              >
                {deltaSemana >= 0 ? "+" : ""}
                {deltaSemana}% vs anterior
              </p>
            )}
          </Card>
        </div>

        {/* Grid principal */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          <div className="xl:col-span-5">
            <CardRepo data={data} />
          </div>
          <div className="xl:col-span-7">
            <CardVelocity data={data} />
          </div>

          <div className="xl:col-span-5">
            <CardActividad data={data} />
          </div>
          <div className="xl:col-span-7">
            <CardCI data={data} />
          </div>

          <div className="xl:col-span-4">
            <CardLenguajes data={data} />
          </div>
          <div className="xl:col-span-8">
            <CardRoadmap roadmap={roadmap} />
          </div>

          <div className="xl:col-span-7">
            <CardBuildLog data={data} />
          </div>
          <div className="xl:col-span-5">
            <CardDeploys data={data} />
          </div>

          <div className="xl:col-span-7">
            <CardCommits commits={data?.commits ?? null} />
          </div>
          <div className="xl:col-span-5 space-y-5">
            <CardPRs data={data} />
            <CardCodeHealth data={data} />
          </div>
        </div>
      </main>
    </div>
  );
}
