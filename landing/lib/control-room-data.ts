import agentRunsIndex from "../data/agent-runs-index.json";

export type RiesgoRun = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type EstadoRun = "merged" | "open" | "completed" | "partial" | "blocked";

export interface AgentRunResumen {
  runId: string;
  fecha: string;
  riesgo: RiesgoRun;
  estado: EstadoRun | string;
  objetivo: string;
  branch: string;
  pr: number | null;
  commit: string;
  agentes: string[];
  archivosResumen: string[];
  verificaciones: string[];
  costoEstimado: string;
  riesgosResiduales: string[];
  proximaAccion: string;
}

export interface ControlRoomData {
  schemaVersion: number;
  generatedAt: string;
  source: string;
  note: string;
  runs: AgentRunResumen[];
}

export interface AgentRunsSummary {
  total: number;
  porRiesgo: Record<RiesgoRun, number>;
  costosEstimados: string[];
  proximaAccion: string;
}

type RawRun = {
  run_id: string;
  fecha: string;
  riesgo: RiesgoRun;
  estado: string;
  objetivo: string;
  branch: string;
  pr: number | null;
  commit: string;
  agentes: string[];
  archivos_resumen: string[];
  verificaciones: string[];
  costo_estimado: string;
  riesgos_residuales: string[];
  proxima_accion: string;
};

type RawIndex = {
  schema_version: number;
  generated_at: string;
  source: string;
  note: string;
  runs: RawRun[];
};

const rawIndex = agentRunsIndex as RawIndex;

function mapRun(run: RawRun): AgentRunResumen {
  return {
    runId: run.run_id,
    fecha: run.fecha,
    riesgo: run.riesgo,
    estado: run.estado,
    objetivo: run.objetivo,
    branch: run.branch,
    pr: run.pr,
    commit: run.commit,
    agentes: run.agentes,
    archivosResumen: run.archivos_resumen,
    verificaciones: run.verificaciones,
    costoEstimado: run.costo_estimado,
    riesgosResiduales: run.riesgos_residuales,
    proximaAccion: run.proxima_accion,
  };
}

export function obtenerControlRoomData(): ControlRoomData {
  return {
    schemaVersion: rawIndex.schema_version,
    generatedAt: rawIndex.generated_at,
    source: rawIndex.source.endsWith("index.json")
      ? rawIndex.source
      : `${rawIndex.source}/index.json`,
    note: rawIndex.note,
    runs: rawIndex.runs.map(mapRun),
  };
}

export function resumirAgentRuns(runs: AgentRunResumen[]): AgentRunsSummary {
  const porRiesgo: Record<RiesgoRun, number> = {
    LOW: 0,
    MEDIUM: 0,
    HIGH: 0,
    CRITICAL: 0,
  };

  for (const run of runs) {
    porRiesgo[run.riesgo] += 1;
  }

  return {
    total: runs.length,
    porRiesgo,
    costosEstimados: runs.map((run) => run.costoEstimado).filter(Boolean),
    proximaAccion: runs.at(-1)?.proximaAccion ?? "Registrar el próximo agent-run.",
  };
}
