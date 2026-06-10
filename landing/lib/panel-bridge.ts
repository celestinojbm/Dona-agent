// landing/lib/panel-bridge.ts
// Bridge del panel de ingeniería → GitHub API + Render API.
//
// Server-side ONLY: lee PANEL_GITHUB_TOKEN/GITHUB_TOKEN y RENDER_API_KEY de
// env. Las keys NUNCA llegan al cliente — el route handler
// /api/engineering/data llama acá y devuelve solo datos ya transformados
// (mismo principio que internal-bridge.ts).
//
// Estrategia best-effort: cada sección (repo, velocity, CI, deploys, PRs,
// commits) se consulta en paralelo; si una falla, se anota en `errores` y el
// resto del panel sigue vivo. Un poll cada ~60s hace ~9 requests a GitHub
// (límite autenticado: 5000/h — sobra margen).
import "server-only";

import type {
  CIRun,
  CommitInfo,
  DeployInfo,
  PanelData,
  PRInfo,
  RepoStats,
} from "./panel-types";

const FETCH_TIMEOUT_MS = 10_000;

/** repo por defecto; override con PANEL_GITHUB_REPO (formato owner/repo). */
const REPO_DEFAULT = "celestinojbm/Dona-agent";

// IDs de servicios Render (no son secretos; la key sí). Overrideables por env.
const RENDER_WEB_ID_DEFAULT = "srv-d6u090cr85hc73fggpu0";
const RENDER_WORKER_ID_DEFAULT = "srv-d7j6fb67r5hc73cic630";

// ── Helpers puros (exportados para tests) ──────────────────────────────────

/**
 * Extrae el total de commits del header `Link` de
 * GET /repos/{repo}/commits?per_page=1: la página `rel="last"` ES el total
 * (1 commit por página). Si no hay header (repo con 1 commit) devuelve
 * `fallback`.
 */
export function totalDesdeLinkHeader(
  link: string | null,
  fallback: number,
): number {
  if (!link) return fallback;
  const m = link.match(/[?&]page=(\d+)>;\s*rel="last"/);
  if (!m) return fallback;
  const n = parseInt(m[1], 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

/** Duración en segundos entre dos timestamps ISO; null si falta alguno o es inválida. */
export function duracionSegundos(
  inicio: string | null | undefined,
  fin: string | null | undefined,
): number | null {
  if (!inicio || !fin) return null;
  const t0 = Date.parse(inicio);
  const t1 = Date.parse(fin);
  if (Number.isNaN(t0) || Number.isNaN(t1) || t1 < t0) return null;
  return Math.round((t1 - t0) / 1000);
}

/** Primera línea de un mensaje de commit, truncada. */
export function primeraLinea(mensaje: string, max = 90): string {
  const linea = (mensaje ?? "").split("\n")[0].trim();
  return linea.length > max ? linea.slice(0, max - 1) + "…" : linea;
}

// ── Fetch con timeout ──────────────────────────────────────────────────────

async function fetchJson<T>(
  url: string,
  headers: Record<string, string>,
): Promise<{ data: T; linkHeader: string | null }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { headers, signal: controller.signal });
    if (!res.ok) {
      // No incluimos body en el error: con que el status llegue al log basta.
      throw new Error(`HTTP ${res.status}`);
    }
    const data = (await res.json()) as T;
    return { data, linkHeader: res.headers.get("link") };
  } finally {
    clearTimeout(timeout);
  }
}

// ── GitHub ─────────────────────────────────────────────────────────────────

function githubHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

// Formas mínimas de las respuestas de la API de GitHub que consumimos.
type GHRepo = { open_issues_count: number };
type GHCommit = {
  sha: string;
  html_url: string;
  commit: {
    message: string;
    author: { name?: string; date?: string } | null;
  };
};
type GHPull = {
  number: number;
  title: string;
  draft: boolean;
  html_url: string;
  created_at: string;
  merged_at: string | null;
  head: { ref: string };
  user: { login: string } | null;
};
type GHRun = {
  id: number;
  name: string;
  head_branch: string;
  status: string;
  conclusion: string | null;
  run_started_at: string;
  updated_at: string;
  html_url: string;
};
type GHParticipation = { all: number[] };

function mapPR(p: GHPull): PRInfo {
  return {
    numero: p.number,
    titulo: p.title,
    rama: p.head?.ref ?? "",
    autor: p.user?.login ?? "?",
    creado_en: p.created_at,
    mergeado_en: p.merged_at,
    draft: Boolean(p.draft),
    url: p.html_url,
  };
}

// ── Render ─────────────────────────────────────────────────────────────────

// La lista de deploys de Render viene envuelta en cursores:
// [{ deploy: {...}, cursor: "..." }, ...]
type RenderDeployWrapper = { deploy?: RenderDeploy } & RenderDeploy;
type RenderDeploy = {
  id?: string;
  status?: string;
  createdAt?: string;
  finishedAt?: string | null;
  commit?: { id?: string; message?: string };
};

/** Normaliza la respuesta de Render (con o sin wrapper de cursor). */
export function mapRenderDeploy(raw: RenderDeployWrapper): DeployInfo | null {
  const d = raw?.deploy ?? raw;
  if (!d || !d.status) return null;
  return {
    estado: d.status,
    commit_corto: (d.commit?.id ?? "").slice(0, 7),
    mensaje: primeraLinea(d.commit?.message ?? ""),
    creado_en: d.createdAt ?? "",
    finalizado_en: d.finishedAt ?? null,
    duracion_segundos: duracionSegundos(d.createdAt, d.finishedAt),
  };
}

async function fetchDeploy(
  serviceId: string,
  apiKey: string,
): Promise<DeployInfo | null> {
  const { data } = await fetchJson<RenderDeployWrapper[]>(
    `https://api.render.com/v1/services/${serviceId}/deploys?limit=1`,
    { Authorization: `Bearer ${apiKey}`, Accept: "application/json" },
  );
  if (!Array.isArray(data) || data.length === 0) return null;
  return mapRenderDeploy(data[0]);
}

// ── Orquestación ───────────────────────────────────────────────────────────

/**
 * Consulta GitHub + Render en paralelo y arma el PanelData completo.
 * Nunca lanza: las secciones que fallan quedan en null + entrada en errores.
 */
export async function fetchPanelData(): Promise<PanelData> {
  const repo = process.env.PANEL_GITHUB_REPO?.trim() || REPO_DEFAULT;
  const ghToken =
    process.env.PANEL_GITHUB_TOKEN?.trim() ||
    process.env.GITHUB_TOKEN?.trim() ||
    "";
  const renderKey = process.env.RENDER_API_KEY?.trim() || "";
  const webId = process.env.PANEL_RENDER_WEB_ID?.trim() || RENDER_WEB_ID_DEFAULT;
  const workerId =
    process.env.PANEL_RENDER_WORKER_ID?.trim() || RENDER_WORKER_ID_DEFAULT;

  const errores: string[] = [];
  const gh = `https://api.github.com/repos/${repo}`;
  const h = githubHeaders(ghToken);

  // Cada sección es una promesa independiente; el catch anota y devuelve null.
  const seccion = async <T>(
    nombre: string,
    fn: () => Promise<T>,
  ): Promise<T | null> => {
    if (nombre.startsWith("render") ? !renderKey : !ghToken) {
      errores.push(`${nombre}: token no configurado`);
      return null;
    }
    try {
      return await fn();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "unknown";
      console.error(`[PANEL] sección ${nombre} falló: ${msg}`);
      errores.push(`${nombre}: ${msg}`);
      return null;
    }
  };

  const [
    repoInfo,
    totalCommits,
    ramas,
    commitsRecientes,
    prsAbiertosRaw,
    prsCerradosRaw,
    participation,
    runsRaw,
    deployWeb,
    deployWorker,
  ] = await Promise.all([
    seccion("repo", async () => (await fetchJson<GHRepo>(gh, h)).data),
    seccion("total_commits", async () => {
      const { data, linkHeader } = await fetchJson<GHCommit[]>(
        `${gh}/commits?per_page=1`,
        h,
      );
      return totalDesdeLinkHeader(linkHeader, data.length);
    }),
    seccion(
      "ramas",
      async () =>
        (await fetchJson<unknown[]>(`${gh}/branches?per_page=100`, h)).data
          .length,
    ),
    seccion(
      "commits",
      async () =>
        (await fetchJson<GHCommit[]>(`${gh}/commits?per_page=12`, h)).data,
    ),
    seccion(
      "prs_abiertos",
      async () =>
        (await fetchJson<GHPull[]>(`${gh}/pulls?state=open&per_page=20`, h))
          .data,
    ),
    seccion(
      "prs_merged",
      async () =>
        (
          await fetchJson<GHPull[]>(
            `${gh}/pulls?state=closed&sort=updated&direction=desc&per_page=15`,
            h,
          )
        ).data,
    ),
    seccion(
      "velocity",
      async () =>
        (await fetchJson<GHParticipation>(`${gh}/stats/participation`, h))
          .data,
    ),
    seccion(
      "ci",
      async () =>
        (
          await fetchJson<{ workflow_runs: GHRun[] }>(
            `${gh}/actions/runs?per_page=10`,
            h,
          )
        ).data.workflow_runs,
    ),
    seccion("render_web", () => fetchDeploy(webId, renderKey)),
    seccion("render_worker", () => fetchDeploy(workerId, renderKey)),
  ]);

  const prsAbiertos = prsAbiertosRaw?.map(mapPR) ?? null;

  const repoStats: RepoStats | null = repoInfo
    ? {
        nombre: repo,
        total_commits: totalCommits,
        prs_abiertos: prsAbiertos?.length ?? 0,
        // open_issues_count de GitHub incluye PRs abiertos; los restamos
        // para reportar issues "de verdad".
        issues_abiertos: Math.max(
          0,
          repoInfo.open_issues_count - (prsAbiertos?.length ?? 0),
        ),
        ramas: ramas ?? 0,
      }
    : null;

  const commits: CommitInfo[] | null =
    commitsRecientes?.map((c) => ({
      sha_corto: c.sha.slice(0, 7),
      mensaje: primeraLinea(c.commit?.message ?? ""),
      autor: c.commit?.author?.name ?? "?",
      fecha: c.commit?.author?.date ?? "",
      url: c.html_url,
    })) ?? null;

  const ci: CIRun[] | null =
    runsRaw?.map((r) => ({
      id: r.id,
      nombre: r.name,
      rama: r.head_branch,
      estado: r.status,
      conclusion: r.conclusion,
      duracion_segundos:
        r.status === "completed"
          ? duracionSegundos(r.run_started_at, r.updated_at)
          : null,
      iniciado_en: r.run_started_at,
      url: r.html_url,
    })) ?? null;

  // participation.all = 52 semanas (la última es la actual). Tomamos 12.
  // El endpoint /stats puede devolver 202 con body vacío mientras GitHub
  // computa; en ese caso `all` no existe y dejamos la sección en null.
  const velocity =
    participation && Array.isArray(participation.all)
      ? participation.all.slice(-12)
      : null;

  const prsMerged =
    prsCerradosRaw
      ?.filter((p) => p.merged_at)
      .slice(0, 8)
      .map(mapPR) ?? null;

  return {
    generado_en: new Date().toISOString(),
    errores,
    repo: repoStats,
    velocity,
    ci,
    deploys:
      deployWeb !== null || deployWorker !== null
        ? { web: deployWeb, worker: deployWorker }
        : null,
    prs_abiertos: prsAbiertos,
    prs_merged: prsMerged,
    commits,
  };
}
