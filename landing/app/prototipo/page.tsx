import {
  ArrowRight,
  Sparkles,
  FileText,
  ShieldCheck,
  BarChart3,
  Check,
} from "lucide-react";

/* Prototipo de dirección visual — sección HERO.
   Base clara premium (Linear/Stripe) + vitalidad de gradiente contenida (Luma).
   Narrativa canónica: plataforma-agente, no "chatbot de WhatsApp". */

export default function PrototipoHero() {
  return (
    <main className="hero-v2">
      {/* rejilla técnica muy tenue, desvanecida hacia los bordes */}
      <div className="grid-fade pointer-events-none absolute inset-0 z-0" aria-hidden />

      {/* ── Nav ── */}
      <nav className="relative z-20 mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <span className="text-[22px] font-semibold tracking-tight text-[color:var(--ink)]">
          Dona
        </span>
        <div className="hidden items-center gap-8 text-sm text-[color:var(--ink-2)] md:flex">
          <a className="transition-colors hover:text-[color:var(--ink)]" href="#">Plataforma</a>
          <a className="transition-colors hover:text-[color:var(--ink)]" href="#">Cómo funciona</a>
          <a className="transition-colors hover:text-[color:var(--ink)]" href="#">Precios</a>
        </div>
        <div className="flex items-center gap-3">
          <a className="hidden text-sm text-[color:var(--ink-2)] transition-colors hover:text-[color:var(--ink)] sm:block" href="#">
            Entrar
          </a>
          <a className="btn-primary inline-flex cursor-pointer items-center rounded-full px-4 py-2 text-sm font-medium" href="#">
            Empezar
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pt-20 pb-8 text-center md:pt-28">
        <div className="aurora aurora--hero" aria-hidden />

        <span className="hero-mono inline-flex items-center gap-2 rounded-full border border-[color:var(--line)] bg-white/70 px-3.5 py-1.5 text-[12px] uppercase tracking-[0.16em] text-[color:var(--ink-2)] backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--brand)" }} />
          Plataforma-agente de negocio
        </span>

        <h1 className="mx-auto mt-7 max-w-3xl text-[2.9rem] font-semibold leading-[1.04] tracking-tight text-[color:var(--ink)] sm:text-6xl md:text-7xl">
          Convierte intención
          <br />
          en <span className="text-aurora">ejecución real.</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-[color:var(--ink-2)] md:text-xl">
          Dona convierte situaciones, recursos y objetivos en activos, workflows y
          acciones reales — con permisos, créditos, trazabilidad y medición. No solo
          responde: prepara, confirma y ejecuta contigo.
        </p>

        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <a className="btn-primary inline-flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 text-sm font-medium" href="#">
            Empezar con Dona
            <ArrowRight className="h-4 w-4" />
          </a>
          <a className="btn-ghost inline-flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 text-sm font-medium" href="#">
            Ver Dona en acción
          </a>
        </div>

        <p className="hero-mono mt-6 text-[12px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
          Empieza desde WhatsApp · web · voz · archivos
        </p>
      </section>

      {/* ── Prueba de producto: el loop ── */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-28">
        <div className="proof-card mx-auto rounded-2xl p-5 md:p-7">
          {/* entrada / intención */}
          <div className="flex items-center gap-2 rounded-xl border border-[color:var(--line)] bg-[color:var(--bg-soft)] px-4 py-3 text-left">
            <span className="hero-mono text-[11px] uppercase tracking-wider text-[color:var(--muted)]">
              Intención
            </span>
            <span className="ml-1 text-[15px] text-[color:var(--ink)]">
              “Necesito lanzar mi nuevo servicio esta semana.”
            </span>
          </div>

          {/* transformación → outputs del loop */}
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <LoopChip icon={<FileText className="h-4 w-4" />} label="Plan" sub="Playbook y pasos" />
            <LoopChip icon={<Sparkles className="h-4 w-4" />} label="Activos" sub="Copy · diseño · página" />
            <LoopChip
              icon={<ShieldCheck className="h-4 w-4" />}
              label="Acción"
              sub="Permiso · costo · preview"
              accent
            />
            <LoopChip icon={<BarChart3 className="h-4 w-4" />} label="Medición" sub="Resultados y próximo paso" />
          </div>

          {/* pie de control */}
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-[color:var(--line)] pt-4">
            {["Preview antes de ejecutar", "Costo en créditos", "Aprobación humana", "Audit trail"].map((t) => (
              <span key={t} className="inline-flex items-center gap-1.5 text-[13px] text-[color:var(--ink-2)]">
                <Check className="h-3.5 w-3.5" style={{ color: "var(--brand-ink)" }} />
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function LoopChip({
  icon,
  label,
  sub,
  accent = false,
}: {
  icon: React.ReactNode;
  label: string;
  sub: string;
  accent?: boolean;
}) {
  return (
    <div
      className="loop-chip rounded-xl px-4 py-3.5 text-left"
      style={accent ? { borderColor: "rgba(91,91,240,0.35)", boxShadow: "0 8px 24px -16px rgba(91,91,240,0.45)" } : undefined}
    >
      <div
        className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg"
        style={{ background: accent ? "rgba(91,91,240,0.10)" : "var(--bg-soft)", color: accent ? "var(--brand-ink)" : "var(--ink-2)" }}
      >
        {icon}
      </div>
      <div className="text-[15px] font-medium text-[color:var(--ink)]">{label}</div>
      <div className="mt-0.5 text-[12.5px] text-[color:var(--muted)]">{sub}</div>
    </div>
  );
}
