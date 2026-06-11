// landing/lib/panel-bridge.ts
// Bridge del panel de ingeniería → GitHub API + Render API.
//
// Server-side ONLY: lee PANEL_GITHUB_TOKEN/GITHUB_TOKEN y RENDER_API_KEY de
// env. Las keys NUNCA llegan al cliente — el route handler
// /api/engineering/data llama acá y devuelve solo datos ya transformados
// (mismo principio que internal-bridge.ts).
//
// Estrategia best-effort: cada sección (repo, velocity, CI, deploys, PRs,
// commits, lenguajes, actividad) se consulta en paralelo; si una falla, se
// anota en `errores` y el resto del panel sigue vivo. Un poll cada ~60s hace
// ~12 requests a GitHub (límite autenticado: 5000/h — sobra margen).
import "server-only";

import type {
  CIRun,
  CommitInfo,
  DeployInfo,
  DeploysServicio,
  Lenguaje,
  PanelData,
  PasoCI,
  PRInfo,
  PuntoDiario,
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

/** Semana cruda de GET /stats/commit_activity. */
export type SemanaActividad = {
  /** Unix seconds del domingo que abre la semana. */
  week: number;
  /** Commits por día, domingo→sábado. */
  days: number[];
  total: number;
};

/**
 * Serie diaria de commits a partir de commit_activity: aplana las semanas en
 * días con fecha ISO, descarta días futuros (la semana actual viene con ceros
 * para los días que no pasaron) y devuelve los últimos `n`.
 */
export function serieDiaria(
  semanas: SemanaActividad[],
  ahoraMs: number,
  n = 30,
): PuntoDiario[] {
  const puntos: PuntoDiario[] = [];
  for (const s of semanas) {
    if (!Array.isArray(s.days)) continue;
    for (let i = 0; i < s.days.length; i++) {
      const fechaMs = (s.week + i * 86_400) * 1000;
      if (fechaMs > ahoraMs) continue;
      puntos.push({
        fecha: new Date(fechaMs).toISOString().slice(0, 10),
        commits: s.days[i],
      });
    }
  }
  return puntos.slice(-n);
}

/**
 * Commits por día de la semana a partir de GET /stats/punch_card
 * (filas [dia(0=domingo), hora, commits]). Devuelve [Lun..Dom].
 */
export function actividadPorDia(
  filas: number[][] | null | undefined,
): number[] | null {
  if (!Array.isArray(filas) || filas.length === 0) return null;
  const porDiaGH = new Array(7).fill(0); // índice GitHub: 0=domingo
  for (const fila of filas) {
    if (!Array.isArray(fila) || fila.length < 3) continue;
    const [dia, , commits] = fila;
    if (dia >= 0 && dia <= 6) porDiaGH[dia] += commits;
  }
  // Reordenar a [Lun..Dom] para el panel.
  return [...porDiaGH.slice(1), porDiaGH[0]];
}

/**
 * Promedio de horas entre apertura y merge. Se calcula sobre TODA la muestra
 * (no sobre la lista recortada para UI): con slice(0,8) el promedio quedaba
 * sesgado por los 8 con actividad más reciente.
 */
export function promedioHorasMerge(
  prs: { created_at: string; merged_at: string | null }[],
): number | null {
  const horas = prs
    .filter((p) => p.merged_at)
    .map((p) => (Date.parse(p.merged_at!) - Date.parse(p.created_at)) / 3_600_000)
    .filter((h) => Number.isFinite(h) && h >= 0);
  if (horas.length === 0) return null;
  return horas.reduce((a, b) => a + b, 0) / horas.length;
}

/**
 * Top de lenguajes con porcentaje (1 decimal) a partir de GET /languages
 * (mapa nombre→bytes). Agrupa el resto en "Otros".
 */
export function topLenguajes(
  mapa: Record<string, number> | null | undefined,
  max = 5,
): Lenguaje[] | null {
  if (!mapa) return null;
  const entradas = Object.entries(mapa).filter(([, b]) => b > 0);
  const total = entradas.reduce((acc, [, b]) => acc + b, 0);
  if (total <= 0) return null;
  const orden = entradas.sort((a, b) => b[1] - a[1]);
  const top = orden.slice(0, max).map(([nombre, bytes]) => ({
    nombre,
    porcentaje: Math.round((bytes / total) * 1000) / 10,
  }));
  const restoBytes = orden.slice(max).reduce((acc, [, b]) => acc + b, 0);
  if (restoBytes > 0) {
    top.push({
      nombre: "Otros",
      porcentaje: Math.round((restoBytes / total) * 1000) / 10,
    });
  }
  return top;
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
type GHBranch = { name: string };
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
type GHStep = {
  name: string;
  status: string;
  conclusion: string | null;
  started_at: string | null;
  completed_at: string | null;
};
type GHJob = { steps?: GHStep[] };

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

async function fetchDeploysServicio(
  serviceId: string,
  apiKey: string,
): Promise<DeploysServicio | null> {
  const { data } = await fetchJson<RenderDeployWrapper[]>(
    `https://api.render.com/v1/services/${serviceId}/deploys?limit=10`,
    { Authorization: `Bearer ${apiKey}`, Accept: "application/json" },
  );
  if (!Array.isArray(data) || data.length === 0) return null;
  // Render lista del más nuevo al más viejo.
  const deploys = data
    .map(mapRenderDeploy)
    .filter((d): d is DeployInfo => d !== null);
  if (deploys.length === 0) return null;
  const duraciones = deploys
    .map((d) => d.duracion_segundos)
    .filter((s): s is number => s !== null)
    .reverse(); // viejo → nuevo para la sparkline
  return { actual: deploys[0], duraciones };
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
    merged7d,
    commitActivity,
    punchCard,
    lenguajesRaw,
    ciCompleto,
    deploysWeb,
    deploysWorker,
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
        (await fetchJson<GHBranch[]>(`${gh}/branches?per_page=100`, h)).data,
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
        // per_page alto y reordenado por merged_at en código: /pulls solo
        // ordena por updated (cualquier comentario en un PR viejo lo sube
        // y desplaza merges recientes de la muestra).
        (
          await fetchJson<GHPull[]>(
            `${gh}/pulls?state=closed&sort=updated&direction=desc&per_page=50`,
            h,
          )
        ).data,
    ),
    seccion("merged_7d", async () => {
      // Search API: el único endpoint que filtra por fecha de merge exacta.
      const fecha = new Date(Date.now() - 7 * 86_400_000)
        .toISOString()
        .slice(0, 10);
      const q = encodeURIComponent(
        `repo:${repo} is:pr is:merged merged:>=${fecha}`,
      );
      return (
        await fetchJson<{ total_count: number }>(
          `https://api.github.com/search/issues?q=${q}`,
          h,
        )
      ).data.total_count;
    }),
    seccion(
      "velocity",
      async () =>
        (await fetchJson<SemanaActividad[]>(`${gh}/stats/commit_activity`, h))
          .data,
    ),
    seccion(
      "actividad",
      async () =>
        (await fetchJson<number[][]>(`${gh}/stats/punch_card`, h)).data,
    ),
    seccion(
      "lenguajes",
      async () =>
        (await fetchJson<Record<string, number>>(`${gh}/languages`, h)).data,
    ),
    seccion("ci", async () => {
      const runs = (
        await fetchJson<{ workflow_runs: GHRun[] }>(
          `${gh}/actions/runs?per_page=20`,
          h,
        )
      ).data.workflow_runs;
      // Steps del run más reciente (1 fetch extra, secuencial a propósito).
      let pasos: PasoCI[] | null = null;
      if (runs.length > 0) {
        try {
          const jobs = (
            await fetchJson<{ jobs: GHJob[] }>(
              `${gh}/actions/runs/${runs[0].id}/jobs?per_page=5`,
              h,
            )
          ).data.jobs;
          const steps = jobs.flatMap((j) => j.steps ?? []);
          if (steps.length > 0) {
            pasos = steps.map((s) => ({
              nombre: s.name,
              conclusion: s.status === "completed" ? s.conclusion : null,
              iniciado_en: s.started_at,
              duracion_segundos: duracionSegundos(s.started_at, s.completed_at),
            }));
          }
        } catch (err) {
          // Los steps son decorativos: si fallan, el resto de CI sigue.
          const msg = err instanceof Error ? err.message : "unknown";
          console.error(`[PANEL] steps del último run fallaron: ${msg}`);
        }
      }
      return { runs, pasos };
    }),
    seccion("render_web", () => fetchDeploysServicio(webId, renderKey)),
    seccion("render_worker", () => fetchDeploysServicio(workerId, renderKey)),
  ]);

  const prsAbiertos = prsAbiertosRaw?.map(mapPR) ?? null;
  const nombresRamas = ramas?.map((r) => r.name) ?? [];

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
        ramas: nombresRamas.length,
        nombres_ramas: nombresRamas.slice(0, 12),
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
    ciCompleto?.runs.map((r) => ({
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

  // commit_activity = 52 semanas con días (la última es la actual, con ceros
  // en los días futuros). El endpoint /stats puede devolver 202 con body no
  // listo mientras GitHub computa; en ese caso dejamos la sección en null.
  const semanasValidas = Array.isArray(commitActivity)
    ? commitActivity.filter((s) => Array.isArray(s.days))
    : [];
  const velocity =
    semanasValidas.length > 0
      ? semanasValidas.slice(-12).map((s) => s.total)
      : null;
  const velocityDiaria =
    semanasValidas.length > 0 ? serieDiaria(semanasValidas, Date.now()) : null;

  // Mergeados reordenados por merged_at desc; el promedio se calcula sobre
  // TODA la muestra y el slice(0,8) queda solo para la lista visual.
  const mergedOrdenados =
    prsCerradosRaw
      ?.filter((p) => p.merged_at)
      .sort((a, b) => Date.parse(b.merged_at!) - Date.parse(a.merged_at!)) ??
    null;
  const prsMerged = mergedOrdenados?.slice(0, 8).map(mapPR) ?? null;
  const mergeHorasProm = mergedOrdenados
    ? promedioHorasMerge(mergedOrdenados)
    : null;

  return {
    generado_en: new Date().toISOString(),
    errores,
    repo: repoStats,
    velocity,
    velocity_diaria: velocityDiaria,
    actividad_semanal: actividadPorDia(punchCard),
    lenguajes: topLenguajes(lenguajesRaw),
    ci,
    ci_pasos: ciCompleto?.pasos ?? null,
    deploys:
      deploysWeb !== null || deploysWorker !== null
        ? { web: deploysWeb, worker: deploysWorker }
        : null,
    prs_abiertos: prsAbiertos,
    prs_merged: prsMerged,
    prs_merged_7d: merged7d,
    merge_horas_prom: mergeHorasProm,
    commits,
  };
}
