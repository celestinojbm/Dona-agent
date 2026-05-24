import {
  Activity,
  Bot,
  CheckCircle2,
  GitPullRequest,
  Lock,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

const estadoProyecto = [
  { label: "Contexto canónico", value: "En main", tone: "emerald" },
  { label: "Guardrails HIGH", value: "Activos", tone: "emerald" },
  { label: "next_required_action", value: "Contrato en main", tone: "sky" },
  { label: "msi / VPS", value: "Sincronizados", tone: "violet" },
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

const hitos = [
  {
    pr: "PR #45",
    titulo: "Contexto canónico distribuido",
    detalle: "AGENTS.md, CLAUDE.md y visión operativa para agentes.",
  },
  {
    pr: "PR #46",
    titulo: "HIGH bloqueado en endpoint genérico",
    detalle: "El Action Center ya no ejecuta HIGH desde controles genéricos.",
  },
  {
    pr: "PR #47",
    titulo: "Confirmación dedicada visible",
    detalle: "HIGH approved queda como pendiente de confirmación dedicada.",
  },
  {
    pr: "PR #48",
    titulo: "Contrato next_required_action",
    detalle: "Backend y dashboard comparten el siguiente control requerido.",
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
    return "border-emerald-400/20 bg-emerald-400/[0.07] text-emerald-200/80";
  }
  if (tone === "sky") {
    return "border-sky-400/20 bg-sky-400/[0.07] text-sky-200/80";
  }
  return "border-violet-400/20 bg-violet-400/[0.07] text-violet-200/80";
}

export default function SeccionControlRoom() {
  return (
    <section className="space-y-6" aria-labelledby="control-room-title">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] font-light uppercase tracking-[0.22em] text-white/35">
            <Activity className="h-3.5 w-3.5" />
            Project Progress · Snapshot 2026-05-24
          </div>
          <h2
            id="control-room-title"
            className="text-2xl font-light tracking-[-0.03em] text-white"
          >
            Dona Control Room
          </h2>
          <p className="mt-2 max-w-2xl text-sm font-light leading-relaxed text-white/45">
            Panel interno para Celestino/Hermes: progreso, orquestación de agentes,
            guardrails y próximos pasos sin convertir a Dona en una caja negra.
          </p>
        </div>
        <div className="rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-4 py-2 text-xs font-light text-emerald-200/80">
          Snapshot 2026-05-24 · Main limpio · Vercel verde
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {estadoProyecto.map((item) => (
          <div key={item.label} className="glass-card rounded-2xl px-5 py-4">
            <p className="text-[11px] font-light uppercase tracking-[0.18em] text-white/25">
              {item.label}
            </p>
            <div
              className={`mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-light ${chipTone(item.tone)}`}
            >
              {item.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="glass-card rounded-3xl p-6">
          <div className="mb-5 flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-white/35">
            <Bot className="h-4 w-4" />
            Agentes y roles
          </div>
          <div className="space-y-3">
            {agentes.map((agente) => (
              <div
                key={agente.nombre}
                className="rounded-2xl border border-white/[0.06] bg-white/[0.025] px-4 py-4"
              >
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="text-sm font-normal text-white">
                    {agente.nombre}
                  </h3>
                  <span className="text-[11px] font-mono text-white/25">
                    {agente.rol}
                  </span>
                </div>
                <p className="mt-2 text-xs font-light leading-relaxed text-white/45">
                  {agente.estado}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card rounded-3xl p-6">
          <div className="mb-5 flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-white/35">
            <GitPullRequest className="h-4 w-4" />
            Hitos recientes
          </div>
          <div className="space-y-4">
            {hitos.map((hito) => (
              <div key={hito.pr} className="relative pl-6">
                <div className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-white/35" />
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-white/35">
                    {hito.pr}
                  </span>
                  <span className="text-sm font-normal text-white/80">
                    {hito.titulo}
                  </span>
                </div>
                <p className="mt-1 text-xs font-light leading-relaxed text-white/40">
                  {hito.detalle}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card rounded-3xl p-6">
          <div className="mb-4 flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-white/35">
            <ShieldCheck className="h-4 w-4" />
            Guardrails
          </div>
          <div className="space-y-3">
            {guardrails.map((g) => (
              <div key={g} className="flex gap-3 text-sm font-light text-white/55">
                <Lock className="mt-0.5 h-4 w-4 shrink-0 text-amber-200/60" />
                <span>{g}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card rounded-3xl p-6">
          <div className="mb-4 flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-white/35">
            <Workflow className="h-4 w-4" />
            Próximos pasos
          </div>
          <div className="space-y-3">
            {proximosPasos.map((paso) => (
              <div key={paso} className="flex gap-3 text-sm font-light text-white/55">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200/60" />
                <span>{paso}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-white/[0.06] bg-white/[0.025] p-4">
            <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-white/30">
              <Sparkles className="h-3.5 w-3.5" />
              Semilla de producto
            </div>
            <p className="text-xs font-light leading-relaxed text-white/45">
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
