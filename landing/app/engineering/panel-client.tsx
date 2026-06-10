"use client";

// landing/app/engineering/panel-client.tsx
// UI del panel de ingeniería. Hace polling a /api/engineering/data cada 60s
// y renderiza las cards (GitHub + Actions + Render + roadmap estático).
//
// Estética: dark editorial (headers en MAYÚSCULAS con tracking, números en
// mono, glass cards) — misma familia visual del resto del landing.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  CIRun,
  CommitInfo,
  DeployInfo,
  PanelData,
  PRInfo,
  Roadmap,
} from "@/lib/panel-types";

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

function duracionLegible(seg: number | null): string {
  if (seg === null || seg < 0) return "—";
  if (seg < 60) return `${seg}s`;
  const m = Math.floor(seg / 60);
  return `${m}m ${seg % 60}s`;
}

function numero(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("es");
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
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass-card rounded-2xl p-6 ${className}`}>
      {children}
    </section>
  );
}

/** Punto de estado: verde ok, rojo falla, ámbar corriendo, gris desconocido. */
function Punto({ tono }: { tono: "ok" | "error" | "curso" | "neutro" }) {
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

function tonoRun(run: CIRun): "ok" | "error" | "curso" | "neutro" {
  if (run.estado !== "completed") return "curso";
  if (run.conclusion === "success") return "ok";
  if (run.conclusion === "failure") return "error";
  return "neutro";
}

function tonoDeploy(d: DeployInfo | null): "ok" | "error" | "curso" | "neutro" {
  if (!d) return "neutro";
  if (d.estado === "live") return "ok";
  if (d.estado.includes("fail")) return "error";
  if (d.estado.includes("progress") || d.estado === "created") return "curso";
  return "neutro";
}

function Stat({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <p className="font-mono text-3xl font-extralight text-gradient-stat">
        {valor}
      </p>
      <p className="text-xs text-white/40 mt-1 uppercase tracking-wider">
        {etiqueta}
      </p>
    </div>
  );
}

// ── Cards ──────────────────────────────────────────────────────────────────

function CardRepo({ data }: { data: PanelData }) {
  return (
    <Card>
      <TituloCard>Repository Analytics</TituloCard>
      <div className="grid grid-cols-2 gap-6">
        <Stat etiqueta="Commits" valor={numero(data.repo?.total_commits)} />
        <Stat etiqueta="PRs abiertos" valor={numero(data.repo?.prs_abiertos)} />
        <Stat
          etiqueta="Issues abiertos"
          valor={numero(data.repo?.issues_abiertos)}
        />
        <Stat etiqueta="Ramas" valor={numero(data.repo?.ramas)} />
      </div>
    </Card>
  );
}

function CardVelocity({ velocity }: { velocity: number[] | null }) {
  const max = velocity && velocity.length ? Math.max(...velocity, 1) : 1;
  return (
    <Card>
      <TituloCard>Commit velocity · 12 semanas</TituloCard>
      {velocity ? (
        <div className="flex items-end gap-2 h-32">
          {velocity.map((v, i) => (
            <div
              key={i}
              className="flex-1 flex flex-col items-center gap-1.5"
              title={`${v} commits`}
            >
              <span className="font-mono text-[10px] text-white/35">{v}</span>
              <div
                className={`w-full rounded-sm transition-all ${
                  i === velocity.length - 1 ? "bg-[#7C3AED]/80" : "bg-white/15"
                }`}
                style={{ height: `${Math.max(4, (v / max) * 100)}%` }}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-white/35">Sin datos (GitHub computando)</p>
      )}
      <p className="text-[10px] text-white/30 mt-3 font-mono">
        última barra = semana actual
      </p>
    </Card>
  );
}

function CardCI({ runs }: { runs: CIRun[] | null }) {
  return (
    <Card>
      <TituloCard>CI/CD Pipelines · GitHub Actions</TituloCard>
      {runs && runs.length ? (
        <ul className="space-y-3">
          {runs.slice(0, 6).map((r) => (
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
              <span className="font-mono text-xs text-white/35 truncate max-w-[10rem]">
                {r.rama}
              </span>
              <span className="font-mono text-xs text-white/35 ml-auto shrink-0">
                {duracionLegible(r.duracion_segundos)} ·{" "}
                {haceCuanto(r.iniciado_en)}
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

function FilaDeploy({
  nombre,
  deploy,
}: {
  nombre: string;
  deploy: DeployInfo | null;
}) {
  return (
    <li className="flex items-center gap-3 text-sm py-2">
      <Punto tono={tonoDeploy(deploy)} />
      <span className="uppercase tracking-wider text-xs text-white/60 w-16 shrink-0">
        {nombre}
      </span>
      {deploy ? (
        <>
          <span className="font-mono text-xs text-white/80">
            {deploy.estado}
          </span>
          <span className="font-mono text-xs text-white/35 truncate">
            {deploy.commit_corto} · {deploy.mensaje}
          </span>
          <span className="font-mono text-xs text-white/35 ml-auto shrink-0">
            {duracionLegible(deploy.duracion_segundos)} ·{" "}
            {haceCuanto(deploy.creado_en)}
          </span>
        </>
      ) : (
        <span className="text-xs text-white/35">sin datos</span>
      )}
    </li>
  );
}

function CardDeploys({ data }: { data: PanelData }) {
  return (
    <Card>
      <TituloCard>Deploys · Render</TituloCard>
      <ul className="divide-y divide-white/5">
        <FilaDeploy nombre="Web" deploy={data.deploys?.web ?? null} />
        <FilaDeploy nombre="Worker" deploy={data.deploys?.worker ?? null} />
      </ul>
    </Card>
  );
}

function CardRoadmap({ roadmap }: { roadmap: Roadmap }) {
  const estilo: Record<string, { punto: "ok" | "error" | "curso" | "neutro"; texto: string }> = {
    hecho: { punto: "ok", texto: "text-white/40 line-through" },
    en_curso: { punto: "curso", texto: "text-white" },
    siguiente: { punto: "neutro", texto: "text-white/80" },
    pendiente: { punto: "neutro", texto: "text-white/50" },
  };
  return (
    <Card>
      <TituloCard>
        {roadmap.titulo} · act. {roadmap.actualizado}
      </TituloCard>
      <ul className="space-y-2.5">
        {roadmap.items.map((item) => {
          const e = estilo[item.estado] ?? estilo.pendiente;
          return (
            <li key={item.id} className="flex items-center gap-3 text-sm">
              <Punto tono={e.punto} />
              <span className="font-mono text-xs text-white/35 w-12 shrink-0">
                {item.id}
              </span>
              <span className={`truncate ${e.texto}`}>{item.nombre}</span>
              {item.detalle && (
                <span className="font-mono text-[10px] text-white/30 ml-auto shrink-0">
                  {item.detalle}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function FilaPR({ pr }: { pr: PRInfo }) {
  return (
    <li className="flex items-center gap-3 text-sm">
      <Punto tono={pr.mergeado_en ? "ok" : pr.draft ? "neutro" : "curso"} />
      <span className="font-mono text-xs text-white/35 shrink-0">
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
      <span className="font-mono text-xs text-white/35 ml-auto shrink-0">
        {haceCuanto(pr.mergeado_en ?? pr.creado_en)}
      </span>
    </li>
  );
}

function CardPRs({ data }: { data: PanelData }) {
  return (
    <Card>
      <TituloCard>Pull Requests</TituloCard>
      <p className="text-xs uppercase tracking-wider text-white/40 mb-3">
        Abiertos
      </p>
      {data.prs_abiertos && data.prs_abiertos.length ? (
        <ul className="space-y-2.5 mb-6">
          {data.prs_abiertos.map((pr) => (
            <FilaPR key={pr.numero} pr={pr} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-white/35 mb-6">Ninguno</p>
      )}
      <p className="text-xs uppercase tracking-wider text-white/40 mb-3">
        Mergeados recientes
      </p>
      {data.prs_merged && data.prs_merged.length ? (
        <ul className="space-y-2.5">
          {data.prs_merged.slice(0, 5).map((pr) => (
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
        <ul className="space-y-2.5">
          {commits.map((c) => (
            <li key={c.sha_corto} className="flex items-center gap-3 text-sm">
              <a
                href={c.url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-xs text-[#7C3AED] hover:text-white transition-colors shrink-0"
              >
                {c.sha_corto}
              </a>
              <span className="truncate text-white/70">{c.mensaje}</span>
              <span className="font-mono text-xs text-white/35 ml-auto shrink-0">
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

function CardCodeHealth() {
  return (
    <Card>
      <TituloCard>Code Health</TituloCard>
      <div className="grid grid-cols-3 gap-6">
        <Stat etiqueta="Coverage" valor="—" />
        <Stat etiqueta="Quality" valor="—" />
        <Stat etiqueta="Tech debt" valor="—" />
      </div>
      <p className="text-[10px] text-white/30 mt-4 font-mono">
        v2 · métricas por definir (no inventamos números)
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

  const ultimoRunMain = data?.ci?.find((r) => r.rama === "main") ?? null;
  const commitsSemana = data?.velocity?.[data.velocity.length - 1] ?? null;

  return (
    <main className="min-h-screen px-6 py-10 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex flex-wrap items-baseline gap-4 mb-10">
        <div>
          <p className="font-mono text-xs tracking-[0.3em] text-white/40 uppercase">
            Dona · Engineering
          </p>
          <h1 className="text-3xl font-extralight tracking-wide uppercase mt-1">
            Control de ingeniería
          </h1>
        </div>
        <div className="ml-auto flex items-center gap-4 text-xs font-mono text-white/40">
          {error ? (
            <span className="text-red-400">{error}</span>
          ) : (
            <span>
              {actualizado
                ? `actualizado ${haceCuanto(actualizado.toISOString())}`
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
            className="btn-secondary rounded-md px-3 py-1.5 uppercase tracking-wider"
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
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-2">
            CI · main
          </p>
          <div className="flex items-center gap-2">
            <Punto tono={ultimoRunMain ? tonoRun(ultimoRunMain) : "neutro"} />
            <span className="font-mono text-sm">
              {ultimoRunMain
                ? (ultimoRunMain.conclusion ?? ultimoRunMain.estado)
                : "—"}
            </span>
          </div>
        </Card>
        <Card>
          <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-2">
            Deploy web
          </p>
          <div className="flex items-center gap-2">
            <Punto tono={tonoDeploy(data?.deploys?.web ?? null)} />
            <span className="font-mono text-sm">
              {data?.deploys?.web?.estado ?? "—"}
            </span>
          </div>
        </Card>
        <Card>
          <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-2">
            Commits semana
          </p>
          <span className="font-mono text-sm">{numero(commitsSemana)}</span>
        </Card>
        <Card>
          <p className="text-[10px] uppercase tracking-[0.2em] text-white/40 mb-2">
            PRs abiertos
          </p>
          <span className="font-mono text-sm">
            {numero(data?.repo?.prs_abiertos)}
          </span>
        </Card>
      </div>

      {/* Grid principal */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CardRepo data={data ?? vacio()} />
        <CardVelocity velocity={data?.velocity ?? null} />
        <CardCI runs={data?.ci ?? null} />
        <CardDeploys data={data ?? vacio()} />
        <CardRoadmap roadmap={roadmap} />
        <CardPRs data={data ?? vacio()} />
        <CardCommits commits={data?.commits ?? null} />
        <CardCodeHealth />
      </div>
    </main>
  );
}

/** PanelData vacío para el primer render (skeleton barato: todo "—"). */
function vacio(): PanelData {
  return {
    generado_en: "",
    errores: [],
    repo: null,
    velocity: null,
    ci: null,
    deploys: null,
    prs_abiertos: null,
    prs_merged: null,
    commits: null,
  };
}
