import {
  Activity,
  Bot,
  CheckCircle2,
  FileText,
  Lock,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import {
  obtenerControlRoomData,
  resumirAgentRuns,
} from "@/lib/control-room-data";

const estadoProyecto = [
  { label: "Contexto canónico", value: "En main", tone: "emerald" },
  { label: "Run Ledger", value: "Obligatorio", tone: "emerald" },
  { label: "Agent-runs", value: "Index estático", tone: "sky" },
  { label: "APIs vivas", value: "Pendientes", tone: "violet" },
] as const;

const agentes = [
  {
    nombre: "Hermes",
    rol: "Orquestador técnico y guardián de contexto",
    estado: "Dirige scope, tests, PRs y decisiones",
  },
  {
    nombre: "Claude Code",
    rol: "Implementador principal",
    estado: "Escribe código en workspace limpio msi",
  },
  {
    nombre: "Codex",
    rol: "Revisor técnico independiente",
    estado: "Audita diffs, riesgos y tests faltantes",
  },
  {
    nombre: "OpenClaw",
    rol: "Auditor de visión y memoria histórica",
    estado: "Referencia estratégica, no fuente canónica de código",
  },
] as const;

const guardrails = [
  "No ejecutar acciones reales sin permiso humano, preview, costo y riesgo.",
  "No reducir Dona a chatbot, CRM estrecho o WhatsApp assistant.",
  "Claude Code y Codex implementan/revisan; Hermes controla scope y PRs.",
  "OpenClaw aporta memoria histórica, pero GitHub/main es código canónico.",
] as const;

const proximosPasos = [
  "Registrar cada agent-run en docs/ops antes o durante el PR.",
  "Automatizar lectura de PRs/checks desde GitHub cuando el shell esté estable.",
  "Convertir este Control Room interno en patrón futuro para iniciativas de usuarios.",
] as const;

function chipTone(tone: "emerald" | "sky" | "violet") {
  if (tone === "emerald") {
    return "border-emerald-600/40 bg-emerald-600/10 text-emerald-700";
  }
  if (tone === "sky") {
    return "border-sky-600/40 bg-sky-600/10 text-sky-700";
  }
  return "border-[#5b5bf0]/30 bg-[color:var(--fill)] text-[color:var(--brand-ink)]";
}

export default function SeccionControlRoom() {
  const controlRoomData = obtenerControlRoomData();
  const resumen = resumirAgentRuns(controlRoomData.runs);

  return (
    <section className="space-y-6" aria-labelledby="control-room-title">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[color:var(--line)] bg-[color:var(--bg-soft)] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.22em] text-[color:var(--muted)]">
            <Activity className="h-3.5 w-3.5" />
            Project Progress · Snapshot 2026-05-24
          </div>
          <h2
            id="control-room-title"
            className="text-2xl font-semibold tracking-[-0.03em] text-[color:var(--ink)]"
          >
            Dona Control Room
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[color:var(--muted)]">
            Panel interno para Celestino/Hermes: progreso, orquestación de agentes,
            guardrails y próximos pasos sin convertir a Dona en una caja negra.
          </p>
        </div>
        <div className="rounded-full border border-emerald-600/40 bg-emerald-600/10 px-4 py-2 text-xs font-medium text-emerald-700">
          {resumen.total} agent-runs · fuente estática {controlRoomData.generatedAt}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {estadoProyecto.map((item) => (
          <div key={item.label} className="surface-card px-5 py-4">
            <p className="eyebrow text-[11px] tracking-[0.18em]">
              {item.label}
            </p>
            <div
              className={`mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${chipTone(item.tone)}`}
            >
              {item.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="surface-card p-6">
          <div className="eyebrow mb-5 flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Agent-runs versionados
          </div>
          <div className="mb-5 rounded-2xl border border-[color:var(--line)] bg-[color:var(--bg-soft)] p-4">
            <p className="text-xs font-mono text-[color:var(--muted)]">
              Fuente: {controlRoomData.source}
            </p>
            <p className="mt-1 text-sm text-[color:var(--ink-2)]">
              {resumen.total} runs · MEDIUM: {resumen.porRiesgo.MEDIUM} · APIs vivas: no conectadas
            </p>
          </div>
          <div className="space-y-4">
            {controlRoomData.runs.map((run) => (
              <div key={run.runId} className="relative pl-6">
                <div className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-[color:var(--muted)]" />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-[color:var(--muted)]">
                    {run.pr ? `PR #${run.pr}` : run.runId}
                  </span>
                  <span className="rounded-full border border-amber-500/40 bg-amber-500/15 px-2 py-0.5 text-[10px] font-mono text-amber-700">
                    {run.riesgo}
                  </span>
                  <span className="text-sm font-medium text-[color:var(--ink-2)]">
                    {run.estado}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-[color:var(--muted)]">
                  {run.objetivo}
                </p>
                <p className="mt-2 text-[11px] leading-relaxed text-[color:var(--muted)]">
                  Costo estimado: {run.costoEstimado}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-[color:var(--muted)]">
                  Próxima acción: {run.proximaAccion}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="surface-card p-6">
          <div className="eyebrow mb-5 flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Agentes y roles
          </div>
          <div className="space-y-3">
            {agentes.map((agente) => (
              <div
                key={agente.nombre}
                className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--bg-soft)] px-4 py-4"
              >
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="text-sm font-semibold text-[color:var(--ink)]">
                    {agente.nombre}
                  </h3>
                  <span className="text-[11px] font-mono text-[color:var(--muted)]">
                    {agente.rol}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-[color:var(--muted)]">
                  {agente.estado}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="surface-card p-6">
          <div className="eyebrow mb-4 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Guardrails
          </div>
          <div className="space-y-3">
            {guardrails.map((g) => (
              <div key={g} className="flex gap-3 text-sm text-[color:var(--ink-2)]">
                <Lock className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
                <span>{g}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="surface-card p-6">
          <div className="eyebrow mb-4 flex items-center gap-2">
            <Workflow className="h-4 w-4" />
            Próximos pasos
          </div>
          <div className="space-y-3">
            {proximosPasos.map((paso) => (
              <div key={paso} className="flex gap-3 text-sm text-[color:var(--ink-2)]">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                <span>{paso}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-[color:var(--line)] bg-[color:var(--bg-soft)] p-4">
            <div className="eyebrow mb-2 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5" />
              Semilla de producto
            </div>
            <p className="text-xs leading-relaxed text-[color:var(--muted)]">
              Este Control Room interno será el patrón para mostrar a usuarios
              qué entendió Dona, qué agentes trabajaron, qué permisos faltan,
              cuánto cuesta y qué resultado produjo.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
