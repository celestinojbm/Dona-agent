// landing/lib/panel-types.ts
// Tipos del panel de ingeniería (/engineering). Viven separados del bridge
// (lib/panel-bridge.ts, que es `server-only`) para que los Client Components
// puedan importarlos sin romper el build.

/** Run de GitHub Actions (CI). */
export type CIRun = {
  id: number;
  nombre: string;
  rama: string;
  /** queued | in_progress | completed */
  estado: string;
  /** success | failure | cancelled | null si sigue corriendo */
  conclusion: string | null;
  duracion_segundos: number | null;
  iniciado_en: string;
  url: string;
};

/** Deploy de Render (web o worker). */
export type DeployInfo = {
  /** live | build_in_progress | update_failed | ... (estados de Render) */
  estado: string;
  commit_corto: string;
  mensaje: string;
  creado_en: string;
  finalizado_en: string | null;
  duracion_segundos: number | null;
};

/** Pull request (abierto o mergeado). */
export type PRInfo = {
  numero: number;
  titulo: string;
  rama: string;
  autor: string;
  creado_en: string;
  mergeado_en: string | null;
  draft: boolean;
  url: string;
};

/** Commit del historial reciente. */
export type CommitInfo = {
  sha_corto: string;
  mensaje: string;
  autor: string;
  fecha: string;
  url: string;
};

/** Estadísticas agregadas del repo. */
export type RepoStats = {
  nombre: string;
  total_commits: number | null;
  prs_abiertos: number;
  issues_abiertos: number;
  ramas: number;
};

/** Payload completo que devuelve GET /api/engineering/data. */
export type PanelData = {
  generado_en: string;
  /** Secciones que fallaron en este poll (best-effort, no aborta el resto). */
  errores: string[];
  repo: RepoStats | null;
  /** Commits por semana, de la más vieja a la actual (hasta 12). */
  velocity: number[] | null;
  ci: CIRun[] | null;
  deploys: {
    web: DeployInfo | null;
    worker: DeployInfo | null;
  } | null;
  prs_abiertos: PRInfo[] | null;
  prs_merged: PRInfo[] | null;
  commits: CommitInfo[] | null;
};

/** Ítem del roadmap (data/panel-roadmap.json). */
export type RoadmapItem = {
  id: string;
  nombre: string;
  estado: "hecho" | "en_curso" | "siguiente" | "pendiente";
  detalle?: string;
};

export type Roadmap = {
  titulo: string;
  actualizado: string;
  items: RoadmapItem[];
};
