"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  ArrowRight,
  Sparkles,
  FileText,
  ShieldCheck,
  BarChart3,
  Check,
  Menu,
  X,
  ChevronDown,
  Workflow,
  Users,
  Brain,
  Zap,
  LayoutDashboard,
  MessageSquare,
  Mic,
  Paperclip,
  Globe,
  Eye,
  Coins,
  AlertTriangle,
  ClipboardCheck,
  ScrollText,
  Gauge,
  Megaphone,
  PenLine,
  LineChart,
  Mail,
  CalendarDays,
  Rocket,
  Building2,
  Store,
  Palette,
} from "lucide-react";

/* ════════════════════════════════════════════════════════════════════════
   Landing pública de Dona — base clara premium (Linear/Stripe) + vitalidad
   de gradiente Luma CONTENIDA. Todo el sistema visual deriva del hero
   aprobado (app/prototipo). Narrativa canónica: plataforma-agente de
   negocio, no "chatbot de WhatsApp" (WhatsApp es solo un canal de entrada).

   Progressive enhancement: TODO el contenido crítico es visible sin JS
   (SSR + reveal opcional). El reveal on-scroll solo se activa con JS y se
   desactiva bajo prefers-reduced-motion.
   ════════════════════════════════════════════════════════════════════════ */

/* ── Datos de la página ── */

const LOOP_PASOS = [
  { icon: MessageSquare, titulo: "Entrada", desc: "Una idea, nota de voz, mensaje, archivo, link o email." },
  { icon: Brain, titulo: "Contexto", desc: "Memoria, herramientas conectadas, historial y objetivos." },
  { icon: Sparkles, titulo: "Producción", desc: "Activos, documentos, diseños, campañas y workflows." },
  { icon: ShieldCheck, titulo: "Permisos", desc: "Preview, riesgo, costo en créditos y aprobación humana." },
  { icon: Zap, titulo: "Ejecución", desc: "Acciones reales autorizadas, con trazabilidad." },
  { icon: BarChart3, titulo: "Medición", desc: "Resultados, aprendizaje y siguiente paso." },
];

const MODULOS = [
  { icon: Palette, nombre: "Studio", linea: "Crea activos y piezas finales: copy, diseño, documentos, páginas.", meta: "Cada activo queda medido y versionado." },
  { icon: Workflow, nombre: "Flow", linea: "Convierte objetivos en workflows y playbooks accionables.", meta: "Con pasos, responsables y estado." },
  { icon: Users, nombre: "Agents", linea: "Coordina agentes especializados con límites claros.", meta: "Cada agente opera bajo permisos y presupuesto." },
  { icon: Brain, nombre: "Memory", linea: "Conserva contexto, decisiones, estilo y preferencias.", meta: "El contexto informa cada acción posterior." },
  { icon: Zap, nombre: "Actions", linea: "Prepara y ejecuta acciones reales — solo con confirmación.", meta: "Preview, costo y aprobación antes de materializar." },
  { icon: LayoutDashboard, nombre: "Control Room", linea: "Mide costo, progreso, riesgo y resultados en un solo lugar.", meta: "Qué agente hizo qué, qué espera aprobación y qué sigue." },
];

const OUTPUTS = [
  { icon: FileText, titulo: "Propuesta comercial", desc: "Documento listo para enviar, con estructura y tono de tu marca." },
  { icon: Megaphone, titulo: "Campaña de lanzamiento", desc: "Mensajes, piezas y plan de publicación coordinados." },
  { icon: PenLine, titulo: "Landing draft", desc: "Borrador de página con jerarquía clara y llamada a la acción." },
  { icon: LineChart, titulo: "Informe ejecutivo", desc: "Análisis y hallazgos sintetizados para decidir rápido." },
  { icon: CalendarDays, titulo: "Calendario de contenido", desc: "Semanas planeadas por canal, tema y formato." },
  { icon: Mail, titulo: "Secuencia de emails", desc: "Serie con objetivo, tono y seguimiento definidos." },
];

const CONTROLES = [
  { icon: Eye, titulo: "Preview antes de ejecutar", desc: "Ves exactamente qué va a pasar antes de que ocurra." },
  { icon: Coins, titulo: "Costo en créditos", desc: "Cada acción con efecto real muestra su costo estimado." },
  { icon: AlertTriangle, titulo: "Nivel de riesgo", desc: "Las acciones sensibles se marcan y piden confirmación explícita." },
  { icon: ClipboardCheck, titulo: "Aprobación humana", desc: "Nada irreversible se ejecuta sin que tú lo confirmes." },
  { icon: ScrollText, titulo: "Audit trail", desc: "Historial de qué se preparó, quién aprobó y qué se ejecutó." },
  { icon: Gauge, titulo: "Límites de gasto", desc: "Topes de créditos y permisos por herramienta que tú defines." },
];

const CASOS = [
  { icon: Rocket, segmento: "Founders", resultado: "De una nota de voz a un plan de lanzamiento con activos y tareas asignadas." },
  { icon: Building2, segmento: "Agencias", resultado: "Propuestas y campañas para varios clientes sin rehacer todo cada vez." },
  { icon: Palette, segmento: "Creadores", resultado: "Un calendario de contenido y piezas listas a partir de una idea suelta." },
  { icon: Megaphone, segmento: "Marketing", resultado: "Secuencias de email y campañas coordinadas, con medición de resultados." },
  { icon: LayoutDashboard, segmento: "Operaciones", resultado: "Workflows repetibles que se ejecutan con aprobación y quedan registrados." },
  { icon: LineChart, segmento: "Ventas", resultado: "Seguimiento a prospectos y propuestas preparadas antes de cada reunión." },
  { icon: Users, segmento: "Consultores", resultado: "Informes y entregables sintetizados desde documentos y datos del cliente." },
  { icon: Store, segmento: "Negocios locales", resultado: "Respuestas, promociones y contenido, con tu permiso en cada envío." },
];

const FAQ = [
  { q: "¿Dona es un chatbot de WhatsApp?", a: "No. Dona es una plataforma-agente de negocio: convierte intención en activos, workflows y acciones reales, con permisos y medición. WhatsApp es uno de los canales de entrada — también puedes empezar desde web, voz o archivos." },
  { q: "¿Dona ejecuta acciones sin preguntarme?", a: "No. Toda acción con costo o efecto irreversible pasa por un paso de preparación con preview, costo en créditos y nivel de riesgo. Solo se materializa cuando tú la confirmas, y queda registrada en el audit trail." },
  { q: "¿Cómo funcionan los créditos?", a: "Las acciones con efecto real (como generar piezas o ejecutar automatizaciones) consumen créditos. Antes de ejecutar, ves el costo estimado. Puedes definir topes de gasto y permisos por herramienta." },
  { q: "¿Es seguro conectar mis herramientas y datos?", a: "Usamos TLS en todas las comunicaciones y ciframos en reposo los datos sensibles (tokens de acceso). No entrenamos modelos con tu información. Trabajamos con un conjunto acotado de proveedores técnicos listados en nuestra política de privacidad." },
  { q: "¿Puedo cancelar cuando quiera?", a: "Sí. No hay contratos ni permanencia. Cancelas desde tu cuenta cuando lo decidas." },
];

const PRICING = [
  {
    plan: "premium" as const,
    nombre: "Premium",
    precio: "$20",
    periodo: "/mes",
    features: [
      "Studio, Flow y Memory",
      "Acciones con preview y aprobación",
      "Créditos incluidos cada mes",
      "Entrada por WhatsApp, web y voz",
      "Audit trail y límites de gasto",
      "Soporte prioritario",
    ],
    destacado: false,
  },
  {
    plan: "pro" as const,
    nombre: "Pro",
    precio: "$40",
    periodo: "/mes",
    features: [
      "Todo lo de Premium",
      "Agents con límites por herramienta",
      "Control Room y medición avanzada",
      "Integraciones y automatizaciones",
      "Multi-negocio",
      "Más créditos incluidos",
    ],
    destacado: true,
  },
];

/* ── Hook de reveal on-scroll (progressive enhancement) ──────────────────
   Marca el contenedor como "ready" solo tras montar en cliente (con JS), lo
   que activa el estado oculto en CSS; luego revela cada [data-reveal] al
   entrar en vista. Sin JS el contenido queda visible por SSR. */
function useReveal() {
  const rootRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    root.setAttribute("data-reveal-root", "ready");
    const items = Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]"));
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.setAttribute("data-reveal", "in");
            obs.unobserve(e.target);
          }
        }
      },
      { rootMargin: "-60px" }
    );
    items.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);
  return rootRef;
}

/* ── Eyebrow + título de sección ── */
function SectionHead({
  eyebrow,
  titulo,
  sub,
}: {
  eyebrow: string;
  titulo: string;
  sub?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-4 text-3xl font-semibold leading-tight tracking-tight text-[color:var(--ink)] sm:text-4xl md:text-[2.75rem]">
        {titulo}
      </h2>
      {sub && (
        <p className="mt-4 text-lg leading-relaxed text-[color:var(--ink-2)]">{sub}</p>
      )}
    </div>
  );
}

/* ── FAQ (acordeón, contenido siempre en el DOM) ── */
function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="surface-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center justify-between gap-4 px-6 py-5 text-left"
      >
        <span className="text-[15px] font-medium text-[color:var(--ink)]">{q}</span>
        <ChevronDown
          className={`h-5 w-5 shrink-0 text-[color:var(--muted)] transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      <div className={open ? "block" : "hidden"}>
        <p className="px-6 pb-5 text-[15px] leading-relaxed text-[color:var(--ink-2)]">
          {a}
        </p>
      </div>
    </div>
  );
}

export default function Home() {
  const [mobileMenu, setMobileMenu] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const rootRef = useReveal();

  // Checkout Stripe — mismo contrato que la landing anterior: POST /api/checkout
  // con { plan }. El endpoint corre 100% server-side y devuelve session.url.
  const handleCheckout = useCallback(async (plan: "premium" | "pro") => {
    setCheckoutLoading(plan);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert(data.error || "No se pudo crear la sesión de pago.");
        setCheckoutLoading(null);
      }
    } catch {
      alert("Error de conexión. Intenta de nuevo.");
      setCheckoutLoading(null);
    }
  }, []);

  const navLinks = [
    { href: "#loop", label: "Cómo funciona" },
    { href: "#modulos", label: "Plataforma" },
    { href: "#control", label: "Control" },
    { href: "#pricing", label: "Precios" },
    { href: "#faq", label: "FAQ" },
  ];

  return (
    <main ref={rootRef} className="relative overflow-x-clip bg-[color:var(--bg)]">
      {/* rejilla técnica muy tenue, desvanecida hacia los bordes */}
      <div className="grid-fade pointer-events-none absolute inset-x-0 top-0 z-0 h-[900px]" aria-hidden />

      {/* ── Nav ── */}
      <nav className="sticky top-0 z-40 border-b border-[color:var(--line)] bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <a href="#" className="text-[22px] font-semibold tracking-tight text-[color:var(--ink)]">
            Dona
          </a>
          <div className="hidden items-center gap-8 text-sm text-[color:var(--ink-2)] md:flex">
            {navLinks.map((l) => (
              <a key={l.href} href={l.href} className="cursor-pointer transition-colors hover:text-[color:var(--ink)]">
                {l.label}
              </a>
            ))}
          </div>
          <div className="hidden items-center gap-3 md:flex">
            <a href="/login" className="cursor-pointer text-sm text-[color:var(--ink-2)] transition-colors hover:text-[color:var(--ink)]">
              Entrar
            </a>
            <a href="#pricing" className="btn-primary inline-flex cursor-pointer items-center rounded-full px-4 py-2 text-sm font-medium">
              Empezar
            </a>
          </div>
          <button
            type="button"
            className="cursor-pointer text-[color:var(--ink-2)] md:hidden"
            onClick={() => setMobileMenu((v) => !v)}
            aria-label="Menú"
            aria-expanded={mobileMenu}
          >
            {mobileMenu ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {mobileMenu && (
          <div className="border-t border-[color:var(--line)] bg-white md:hidden">
            <div className="flex flex-col gap-1 px-6 py-4 text-sm text-[color:var(--ink-2)]">
              {navLinks.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  onClick={() => setMobileMenu(false)}
                  className="cursor-pointer py-2 transition-colors hover:text-[color:var(--ink)]"
                >
                  {l.label}
                </a>
              ))}
              <a href="/login" onClick={() => setMobileMenu(false)} className="cursor-pointer py-2 hover:text-[color:var(--ink)]">
                Entrar
              </a>
              <a
                href="#pricing"
                onClick={() => setMobileMenu(false)}
                className="btn-primary mt-2 inline-flex cursor-pointer items-center justify-center rounded-full px-4 py-2.5 text-sm font-medium"
              >
                Empezar
              </a>
            </div>
          </div>
        )}
      </nav>

      {/* ══════════════════ HERO ══════════════════ */}
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
          <a href="#pricing" className="btn-primary inline-flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
            Empezar con Dona
            <ArrowRight className="h-4 w-4" />
          </a>
          <a href="#loop" className="btn-ghost inline-flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
            Ver Dona en acción
          </a>
        </div>

        <p className="hero-mono mt-6 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-[12px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
          <MessageSquare className="h-3.5 w-3.5" aria-hidden /> WhatsApp
          <span aria-hidden>·</span>
          <Globe className="h-3.5 w-3.5" aria-hidden /> web
          <span aria-hidden>·</span>
          <Mic className="h-3.5 w-3.5" aria-hidden /> voz
          <span aria-hidden>·</span>
          <Paperclip className="h-3.5 w-3.5" aria-hidden /> archivos
        </p>
      </section>

      {/* ══════════════════ PRUEBA DE PRODUCTO: EL LOOP (tarjeta) ══════════════════ */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-24">
        <div className="proof-card mx-auto rounded-2xl p-5 md:p-7">
          <div className="flex items-center gap-2 rounded-xl border border-[color:var(--line)] bg-[color:var(--bg-soft)] px-4 py-3 text-left">
            <span className="hero-mono text-[11px] uppercase tracking-wider text-[color:var(--muted)]">
              Intención
            </span>
            <span className="ml-1 text-[15px] text-[color:var(--ink)]">
              &ldquo;Necesito lanzar mi nuevo servicio esta semana.&rdquo;
            </span>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <LoopChip icon={<FileText className="h-4 w-4" />} label="Plan" sub="Playbook y pasos" />
            <LoopChip icon={<Sparkles className="h-4 w-4" />} label="Activos" sub="Copy · diseño · página" />
            <LoopChip icon={<ShieldCheck className="h-4 w-4" />} label="Acción" sub="Permiso · costo · preview" accent />
            <LoopChip icon={<BarChart3 className="h-4 w-4" />} label="Medición" sub="Resultados y próximo paso" />
          </div>

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

      {/* ══════════════════ DE INTENCIÓN A EJECUCIÓN (loop de 6 pasos) ══════════════════ */}
      <section id="loop" className="relative z-10 mx-auto max-w-6xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="De intención a ejecución"
          titulo="Un solo loop, de la idea al resultado"
          sub="Dona no se detiene en la respuesta. Recorre el ciclo completo — con tu aprobación en los puntos que importan."
        />
        <ol className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {LOOP_PASOS.map((p, i) => {
            const Icon = p.icon;
            return (
              <li
                key={p.titulo}
                data-reveal
                style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                className="surface-card p-6"
              >
                <div className="flex items-center gap-3">
                  <span className="icon-badge h-9 w-9">
                    <Icon className="h-[18px] w-[18px]" />
                  </span>
                  <span className="hero-mono text-[11px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
                    Paso {String(i + 1).padStart(2, "0")}
                  </span>
                </div>
                <h3 className="mt-4 text-lg font-semibold text-[color:var(--ink)]">{p.titulo}</h3>
                <p className="mt-1.5 text-[15px] leading-relaxed text-[color:var(--ink-2)]">{p.desc}</p>
              </li>
            );
          })}
        </ol>
      </section>

      {/* ══════════════════ MÓDULOS DE PLATAFORMA ══════════════════ */}
      <section id="modulos" className="relative z-10 border-y border-[color:var(--line)] bg-[color:var(--bg-soft)]">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <SectionHead
            eyebrow="Plataforma"
            titulo="Seis módulos, un sistema con control"
            sub="Cada módulo se conecta con permisos y medición: producir, decidir y ejecutar sin perder el control humano."
          />
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {MODULOS.map((m, i) => {
              const Icon = m.icon;
              return (
                <div
                  key={m.nombre}
                  data-reveal
                  style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                  className="surface-card flex flex-col p-6"
                >
                  <span className="icon-badge h-10 w-10">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-4 text-lg font-semibold text-[color:var(--ink)]">
                    Dona {m.nombre}
                  </h3>
                  <p className="mt-1.5 text-[15px] leading-relaxed text-[color:var(--ink-2)]">{m.linea}</p>
                  <p className="mt-4 border-t border-[color:var(--line)] pt-3 text-[13px] text-[color:var(--muted)]">
                    {m.meta}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ══════════════════ GALERÍA DE OUTPUTS ══════════════════ */}
      <section id="outputs" className="relative z-10 mx-auto max-w-6xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Outputs"
          titulo="Lo que Dona produce"
          sub="No solo features: trabajo real y entregable. Estos son ejemplos de lo que sale del loop."
        />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {OUTPUTS.map((o, i) => {
            const Icon = o.icon;
            return (
              <div
                key={o.titulo}
                data-reveal
                style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                className="surface-card overflow-hidden p-0"
              >
                {/* mockup limpio: cabecera de "documento" con gradiente contenido */}
                <div className="relative flex h-28 items-center justify-center border-b border-[color:var(--line)] bg-[color:var(--bg-soft)]">
                  <div
                    className="pointer-events-none absolute inset-0 opacity-60"
                    style={{
                      background:
                        "radial-gradient(60% 90% at 30% 20%, rgba(99,102,241,0.14), transparent 70%), radial-gradient(50% 80% at 80% 70%, rgba(251,146,108,0.12), transparent 72%)",
                    }}
                    aria-hidden
                  />
                  <span className="icon-badge relative h-11 w-11">
                    <Icon className="h-5 w-5" />
                  </span>
                </div>
                <div className="p-6">
                  <h3 className="text-[15px] font-semibold text-[color:var(--ink)]">{o.titulo}</h3>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-[color:var(--ink-2)]">{o.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════════════════ CONTROL HUMANO Y CONFIANZA (obligatoria) ══════════════════ */}
      <section id="control" className="relative z-10 border-y border-[color:var(--line)] bg-[color:var(--bg-soft)]">
        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
          <SectionHead
            eyebrow="Control humano y confianza"
            titulo="Dona no ejecuta a ciegas"
            sub="Toda acción con costo o efecto irreversible pasa por preparación y confirmación. Tú mandas; Dona deja el rastro."
          />
          <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {CONTROLES.map((c, i) => {
              const Icon = c.icon;
              return (
                <div
                  key={c.titulo}
                  data-reveal
                  style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                  className="surface-card p-6"
                >
                  <span className="icon-badge h-10 w-10">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-4 text-[15px] font-semibold text-[color:var(--ink)]">{c.titulo}</h3>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-[color:var(--ink-2)]">{c.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ══════════════════ CASOS POR SEGMENTO ══════════════════ */}
      <section id="casos" className="relative z-10 mx-auto max-w-6xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Casos"
          titulo="Un resultado concreto para cada quien"
          sub="No etiquetas: resultados. Así se ve Dona según desde dónde trabajes."
        />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CASOS.map((c, i) => {
            const Icon = c.icon;
            return (
              <div
                key={c.segmento}
                data-reveal
                style={{ "--reveal-delay": `${i * 50}ms` } as React.CSSProperties}
                className="surface-card flex flex-col p-6"
              >
                <span className="icon-badge h-9 w-9">
                  <Icon className="h-[18px] w-[18px]" />
                </span>
                <h3 className="mt-4 text-[15px] font-semibold text-[color:var(--ink)]">{c.segmento}</h3>
                <p className="mt-1.5 text-[14px] leading-relaxed text-[color:var(--ink-2)]">{c.resultado}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════════════════ PRICING ══════════════════ */}
      <section id="pricing" className="relative z-10 border-y border-[color:var(--line)] bg-[color:var(--bg-soft)]">
        <div className="mx-auto max-w-5xl px-6 py-20 md:py-28">
          <SectionHead
            eyebrow="Precios"
            titulo="Simple y transparente"
            sub="Elige el plan que se ajuste a tu negocio. Cancela cuando quieras, sin permanencia."
          />
          <div className="mx-auto mt-14 grid max-w-4xl gap-5 md:grid-cols-3">
            {PRICING.map((p) => (
              <div
                key={p.plan}
                className="surface-card flex flex-col p-7"
                style={p.destacado ? { borderColor: "rgba(91,91,240,0.35)" } : undefined}
              >
                {p.destacado && (
                  <span className="hero-mono mb-3 inline-flex w-fit items-center rounded-full bg-[color:var(--brand)]/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-[color:var(--brand-ink)]">
                    Recomendado
                  </span>
                )}
                <p className="eyebrow">{p.nombre}</p>
                <div className="mt-3 flex items-end gap-1">
                  <span className="text-5xl font-semibold tracking-tight text-[color:var(--ink)]">{p.precio}</span>
                  <span className="mb-1.5 text-[color:var(--muted)]">{p.periodo}</span>
                </div>
                <ul className="mt-6 flex-1 space-y-3">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-[14px] text-[color:var(--ink-2)]">
                      <Check className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--brand-ink)" }} />
                      {f}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => handleCheckout(p.plan)}
                  disabled={checkoutLoading === p.plan}
                  className="btn-primary mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-full px-5 py-3 text-sm font-medium"
                >
                  {checkoutLoading === p.plan ? "Redirigiendo…" : "Empezar ahora"}
                </button>
              </div>
            ))}

            {/* Enterprise — próximamente, sin checkout */}
            <div className="surface-soft flex flex-col p-7">
              <div className="flex items-center gap-2">
                <p className="eyebrow">Enterprise</p>
                <span className="hero-mono rounded-full bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]">
                  Próximamente
                </span>
              </div>
              <div className="mt-3 flex items-end gap-1">
                <span className="text-4xl font-semibold tracking-tight text-[color:var(--ink)]">A medida</span>
              </div>
              <ul className="mt-6 flex-1 space-y-3">
                {["Todo lo de Pro", "Equipo y roles", "Límites y auditoría avanzada", "Integraciones a medida", "Onboarding dedicado"].map((f) => (
                  <li key={f} className="flex items-start gap-2 text-[14px] text-[color:var(--ink-2)]">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--muted)]" />
                    {f}
                  </li>
                ))}
              </ul>
              <a
                href="mailto:hola@usadona.com?subject=Dona%20Enterprise"
                className="btn-ghost mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-full px-5 py-3 text-sm font-medium"
              >
                Hablar con nosotros
              </a>
            </div>
          </div>

          <p className="mt-8 flex items-center justify-center gap-2 text-sm text-[color:var(--muted)]">
            <Check className="h-4 w-4" style={{ color: "var(--brand-ink)" }} />
            Cancela cuando quieras. Sin permanencia.
          </p>
        </div>
      </section>

      {/* ══════════════════ CTA FINAL ══════════════════ */}
      <section className="relative z-10 overflow-hidden">
        <div className="relative mx-auto max-w-3xl px-6 py-24 text-center md:py-32">
          <div className="aurora aurora--cta" aria-hidden />
          <h2 className="relative mx-auto max-w-2xl text-3xl font-semibold leading-tight tracking-tight text-[color:var(--ink)] sm:text-4xl md:text-5xl">
            Empieza con una idea. <span className="text-aurora">Dona la convierte en ejecución.</span>
          </h2>
          <p className="relative mx-auto mt-5 max-w-xl text-lg leading-relaxed text-[color:var(--ink-2)]">
            Del primer mensaje al primer resultado — con permisos, costo y medición desde el principio.
          </p>
          <div className="relative mt-9 flex flex-wrap items-center justify-center gap-3">
            <a href="#pricing" className="btn-primary inline-flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
              Empezar con Dona
              <ArrowRight className="h-4 w-4" />
            </a>
            <a href="#loop" className="btn-ghost inline-flex cursor-pointer items-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
              Ver el loop
            </a>
          </div>
        </div>
      </section>

      {/* ══════════════════ FAQ ══════════════════ */}
      <section id="faq" className="relative z-10 border-t border-[color:var(--line)] bg-[color:var(--bg-soft)]">
        <div className="mx-auto max-w-3xl px-6 py-20 md:py-28">
          <SectionHead eyebrow="FAQ" titulo="Preguntas frecuentes" />
          <div className="mt-12 space-y-3">
            {FAQ.map((f) => (
              <FaqItem key={f.q} q={f.q} a={f.a} />
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════ FOOTER ══════════════════ */}
      <footer className="relative z-10 border-t border-[color:var(--line)] bg-white">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <span className="text-xl font-semibold tracking-tight text-[color:var(--ink)]">Dona</span>
              <span className="text-sm text-[color:var(--muted)]">
                Plataforma-agente de negocio y ejecución controlada
              </span>
            </div>
            <div className="flex items-center gap-6 text-sm text-[color:var(--ink-2)]">
              <a href="mailto:hola@usadona.com" className="cursor-pointer transition-colors hover:text-[color:var(--ink)]">
                hola@usadona.com
              </a>
              <a
                href="https://instagram.com/usadonaapp"
                target="_blank"
                rel="noopener noreferrer"
                className="cursor-pointer transition-colors hover:text-[color:var(--ink)]"
              >
                Instagram
              </a>
            </div>
          </div>

          <div className="mt-10 flex flex-col items-start justify-between gap-4 border-t border-[color:var(--line)] pt-8 md:flex-row md:items-center">
            <div className="flex flex-wrap items-center gap-6 text-[13px] text-[color:var(--muted)]">
              <a href="/terminos-y-condiciones" className="cursor-pointer transition-colors hover:text-[color:var(--ink)]">
                Términos y condiciones
              </a>
              <a href="/politica-de-privacidad" className="cursor-pointer transition-colors hover:text-[color:var(--ink)]">
                Política de privacidad
              </a>
              <a href="/soporte" className="cursor-pointer transition-colors hover:text-[color:var(--ink)]">
                Soporte
              </a>
            </div>
            <p className="text-[13px] text-[color:var(--muted)]">
              &copy; {new Date().getFullYear()} Dona. Todos los derechos reservados.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}

/* ── Chip del loop (tarjeta del hero) ── */
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
      style={
        accent
          ? { borderColor: "rgba(91,91,240,0.35)", boxShadow: "0 8px 24px -16px rgba(91,91,240,0.45)" }
          : undefined
      }
    >
      <div
        className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-lg"
        style={{
          background: accent ? "rgba(91,91,240,0.10)" : "var(--bg-soft)",
          color: accent ? "var(--brand-ink)" : "var(--ink-2)",
        }}
      >
        {icon}
      </div>
      <div className="text-[15px] font-medium text-[color:var(--ink)]">{label}</div>
      <div className="mt-0.5 text-[12.5px] text-[color:var(--muted)]">{sub}</div>
    </div>
  );
}
