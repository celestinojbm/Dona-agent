"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Search,
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
   Landing pública de Dona — base clara editorial (case-study premium):
   fondo gris cálido, titulares gigantes a dos líneas, párrafos a dos tonos,
   tarjetas blancas de radio generoso y UN acento violeta. La vitalidad Luma
   vive en el escenario del hero (panel de gradiente + Control Room en un
   monitor, mockup 100% CSS). Narrativa canónica: plataforma-agente de
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

/* Barras de la gráfica del mockup (alturas en %). Zona roja = caída marcada
   con chip negativo; zona violeta = repunte marcado con chip positivo. */
const MOCK_BARRAS = [34, 46, 40, 30, 26, 34, 42, 50, 58, 72, 86, 78, 64, 54, 48, 42, 46, 52, 58, 50, 44, 40];
const MOCK_ZONA_NEG = [2, 3, 4, 5];
const MOCK_ZONA_POS = [9, 10, 11, 12];

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

/* ── Cabecera editorial de sección: eyebrow + titular gigante a la izquierda
   y párrafo a dos tonos a la derecha (patrón case-study). El titular acepta
   "\n" para forzar el corte en dos líneas. ── */
function SectionHead({
  eyebrow,
  titulo,
  sub,
}: {
  eyebrow: string;
  titulo: string;
  sub?: React.ReactNode;
}) {
  const lineas = titulo.split("\n");
  return (
    <div className="grid gap-8 md:grid-cols-[1fr_minmax(0,27rem)] md:items-end md:gap-16">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="mt-5 text-[2.7rem] font-medium leading-[1.04] tracking-tight text-[color:var(--ink)] sm:text-6xl md:text-[4.25rem]">
          {lineas.map((linea, i) => (
            <span key={linea}>
              {linea}
              {i < lineas.length - 1 && <br />}
            </span>
          ))}
        </h2>
      </div>
      {sub && (
        <p className="lead max-w-md text-lg leading-relaxed md:justify-self-end md:pb-2 md:text-xl">
          {sub}
        </p>
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

/* ── Control Room de Dona en un monitor (mockup 100% CSS, datos de ejemplo).
   Es la prueba de producto del hero: nav con los seis módulos, resultados,
   acciones esperando aprobación y créditos con su barra de consumo. ── */
function MockControlRoom() {
  return (
    <div className="mock-screen relative z-10 mx-auto max-w-4xl overflow-hidden">
      <div className="p-4 sm:p-7">
        {/* Topbar: wordmark + módulos + acciones de usuario */}
        <div className="flex items-center justify-between gap-4">
          <span className="text-[17px] font-semibold tracking-tight text-[color:var(--ink)]">Dona</span>
          <div className="hidden items-center gap-1 md:flex">
            <span className="mock-pill-active px-3.5 py-1.5 text-[12px] font-medium">Control Room</span>
            {["Studio", "Flow", "Agents", "Memory", "Actions"].map((m) => (
              <span key={m} className="px-3 py-1.5 text-[12px] text-[color:var(--ink-2)]">
                {m}
              </span>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[color:var(--bg-soft)] text-[color:var(--ink-2)]">
              <Search className="h-3.5 w-3.5" />
            </span>
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[color:var(--bg-soft)] text-[color:var(--ink-2)]">
              <Mail className="h-3.5 w-3.5" />
            </span>
            <span className="grid h-8 w-8 place-items-center rounded-full bg-[color:var(--fill)] text-[11px] font-semibold text-[color:var(--brand-ink)]">
              AL
            </span>
          </div>
        </div>

        {/* Saludo + rango temporal */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <p className="max-w-md text-xl font-medium leading-snug tracking-tight text-[color:var(--ink)] sm:text-2xl">
            Hola, Andrea — esta semana Dona ejecutó{" "}
            <span className="inline-flex translate-y-[-1px] items-center rounded-full border border-[color:var(--line)] bg-white px-3 py-0.5 text-lg shadow-sm sm:text-xl">
              34 acciones
            </span>
          </p>
          <div className="hidden items-center gap-1 sm:flex">
            <span className="px-3 py-1.5 text-[12px] text-[color:var(--ink-2)]">Hoy</span>
            <span className="mock-pill-active px-3.5 py-1.5 text-[12px] font-medium">Semana</span>
            <span className="px-3 py-1.5 text-[12px] text-[color:var(--ink-2)]">Mes</span>
          </div>
        </div>

        {/* Grid principal: gráfica + columna de acciones/créditos */}
        <div className="mt-5 grid gap-4 md:grid-cols-[1.6fr_1fr]">
          {/* Gráfica de resultados */}
          <div className="rounded-2xl border border-[color:var(--line)] p-5">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[14px] font-medium text-[color:var(--ink)]">Resultados de campañas</p>
              <p className="hero-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">30 días</p>
            </div>
            <div className="relative mt-4 h-36">
              <span className="mock-chip-neg absolute left-[8%] top-1 px-2.5 py-1 text-[11px] font-medium">
                Respuestas −9%
              </span>
              <span className="mock-chip-pos absolute left-[42%] top-[-6px] px-2.5 py-1 text-[11px] font-medium">
                Conversión +12%
              </span>
              <div className="absolute inset-x-0 bottom-0 flex h-28 items-end gap-[3px]">
                {MOCK_BARRAS.map((h, i) => {
                  const tono = MOCK_ZONA_POS.includes(i)
                    ? "rgba(91,91,240,0.85)"
                    : MOCK_ZONA_NEG.includes(i)
                      ? "rgba(230,66,99,0.55)"
                      : "rgba(11,11,18,0.10)";
                  return (
                    <span
                      key={i}
                      className="flex-1 rounded-full"
                      style={{ height: `${h}%`, background: tono }}
                    />
                  );
                })}
              </div>
            </div>
            <div className="mt-3 border-t border-dashed border-[color:var(--line)] pt-2">
              <p className="hero-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
                Campañas · emails · seguimientos
              </p>
            </div>
          </div>

          {/* Columna derecha: aprobaciones + créditos */}
          <div className="grid gap-4">
            <div className="rounded-2xl border border-[color:var(--line)] p-5">
              <div className="flex items-center gap-3">
                <span className="surface-fill grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-xl font-medium text-[color:var(--brand-ink)]">
                  03
                </span>
                <p className="text-[14px] font-medium leading-tight text-[color:var(--ink)]">
                  Acciones esperando tu aprobación
                </p>
              </div>
              <p className="mt-3 text-[12.5px] leading-relaxed text-[color:var(--muted)]">
                Con preview, costo en créditos y nivel de riesgo listos.
              </p>
              <span className="mt-4 inline-flex items-center gap-2 rounded-full bg-[color:var(--fill)] px-4 py-2 text-[12px] font-medium text-[color:var(--ink)]">
                Revisar acciones
                <ArrowUpRight className="h-3.5 w-3.5" />
              </span>
            </div>
            <div className="surface-fill p-5">
              <p className="text-[12.5px] text-[color:var(--ink-2)]">Créditos disponibles</p>
              <p className="mt-1 text-3xl font-medium tracking-tight text-[color:var(--ink)]">1.240</p>
              <div className="bar-track mt-4">
                <span className="bar-fill" style={{ width: "62%" }} />
              </div>
              <p className="mt-2 text-[11.5px] text-[color:var(--muted)]">de 2.000 incluidos este mes</p>
            </div>
          </div>
        </div>

        {/* Franja inferior de estado */}
        <div className="mt-5 hidden items-center gap-10 border-t border-[color:var(--line)] pt-4 sm:flex">
          <div>
            <p className="hero-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">Workflows activos</p>
            <p className="mt-0.5 text-lg font-medium text-[color:var(--ink)]">06</p>
          </div>
          <div>
            <p className="hero-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">Activos creados</p>
            <p className="mt-0.5 text-lg font-medium text-[color:var(--ink)]">24</p>
          </div>
          <div>
            <p className="hero-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]">Audit trail</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-lg font-medium text-[color:var(--ink)]">
              Al día
              <Check className="h-4 w-4" style={{ color: "var(--brand-ink)" }} />
            </p>
          </div>
        </div>
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
      <nav className="nav-blur sticky top-0 z-40 border-b border-[color:var(--line)]">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
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
          <div className="border-t border-[color:var(--line)] bg-[color:var(--bg)] md:hidden">
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
      <section className="relative z-10 mx-auto max-w-5xl px-6 pt-24 pb-10 text-center md:pt-32">
        <div className="aurora aurora--hero" aria-hidden />

        <h1 className="mx-auto max-w-4xl text-[3.6rem] font-medium leading-[1.02] tracking-tight text-[color:var(--ink)] sm:text-7xl md:text-8xl">
          Convierte intención
          <br />
          en <span className="text-aurora">ejecución real.</span>
        </h1>

        <p className="lead mx-auto mt-8 max-w-3xl text-xl leading-relaxed md:text-2xl">
          Dona convierte situaciones, recursos y objetivos en{" "}
          <strong>activos, workflows y acciones reales</strong> — con permisos,
          créditos, trazabilidad y medición. No solo responde:{" "}
          <strong>prepara, confirma y ejecuta contigo.</strong>
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <a href="#pricing" className="btn-primary inline-flex cursor-pointer items-center gap-2 rounded-full px-8 py-4 text-base font-medium">
            Empezar con Dona
            <ArrowRight className="h-5 w-5" />
          </a>
          <a href="#loop" className="btn-ghost inline-flex cursor-pointer items-center gap-2 rounded-full px-8 py-4 text-base font-medium">
            Ver Dona en acción
          </a>
        </div>

        <p className="hero-mono mt-8 flex flex-wrap items-center justify-center gap-x-2.5 gap-y-1 text-[13px] uppercase tracking-[0.14em] text-[color:var(--muted)]">
          <MessageSquare className="h-4 w-4" aria-hidden /> WhatsApp
          <span aria-hidden>·</span>
          <Globe className="h-4 w-4" aria-hidden /> web
          <span aria-hidden>·</span>
          <Mic className="h-4 w-4" aria-hidden /> voz
          <span aria-hidden>·</span>
          <Paperclip className="h-4 w-4" aria-hidden /> archivos
        </p>
      </section>

      {/* ══════════════════ PRUEBA DE PRODUCTO: CONTROL ROOM EN ESCENARIO ══════════════════ */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-24 md:pb-28">
        <div className="hero-stage px-5 pt-16 sm:px-12 sm:pt-24">
          <span className="stage-ghost" aria-hidden>
            Dona
          </span>
          <MockControlRoom />
          {/* pie del monitor */}
          <div aria-hidden>
            <div className="mock-stand-neck" />
            <div className="mock-stand-base mb-10" />
          </div>
        </div>

        <div className="mt-7 flex flex-wrap items-center justify-center gap-x-8 gap-y-2">
          {["Preview antes de ejecutar", "Costo en créditos", "Aprobación humana", "Audit trail"].map((t) => (
            <span key={t} className="inline-flex items-center gap-2 text-[15px] text-[color:var(--ink-2)]">
              <Check className="h-4 w-4" style={{ color: "var(--brand-ink)" }} />
              {t}
            </span>
          ))}
        </div>
      </section>

      {/* ══════════════════ DE INTENCIÓN A EJECUCIÓN (loop de 6 pasos) ══════════════════ */}
      <section id="loop" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="De intención a ejecución"
          titulo={"Un solo loop,\nde la idea al resultado"}
          sub={
            <>
              Dona no se detiene en la respuesta. <strong>Recorre el ciclo completo</strong> —
              con tu aprobación en los puntos que importan.
            </>
          }
        />
        <ol className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {LOOP_PASOS.map((p, i) => {
            const Icon = p.icon;
            return (
              <li
                key={p.titulo}
                data-reveal
                style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                className="surface-card p-8"
              >
                <div className="flex items-center justify-between">
                  <span className="surface-fill grid h-12 w-12 place-items-center rounded-2xl text-lg font-medium text-[color:var(--brand-ink)]">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <Icon className="h-5 w-5 text-[color:var(--muted)]" />
                </div>
                <h3 className="mt-6 text-xl font-medium text-[color:var(--ink)]">{p.titulo}</h3>
                <p className="lead mt-2 text-[17px] leading-relaxed">{p.desc}</p>
              </li>
            );
          })}
        </ol>
      </section>

      {/* ══════════════════ MÓDULOS DE PLATAFORMA ══════════════════ */}
      <section id="modulos" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Plataforma"
          titulo={"Seis módulos,\nun sistema con control"}
          sub={
            <>
              Cada módulo se conecta con <strong>permisos y medición</strong>: producir,
              decidir y ejecutar <strong>sin perder el control humano.</strong>
            </>
          }
        />
        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODULOS.map((m, i) => {
            const Icon = m.icon;
            const destacado = m.nombre === "Control Room";
            return (
              <div
                key={m.nombre}
                data-reveal
                style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                className={`${destacado ? "card-gradient" : "surface-card"} flex flex-col p-8`}
              >
                <span
                  className={`grid h-12 w-12 place-items-center rounded-2xl ${
                    destacado ? "bg-white/20 text-white" : "icon-badge"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className={`mt-5 text-xl font-medium ${destacado ? "text-white" : "text-[color:var(--ink)]"}`}>
                  Dona {m.nombre}
                </h3>
                <p className={`mt-2 text-[17px] leading-relaxed ${destacado ? "text-white/85" : "text-[color:var(--muted)]"}`}>
                  {m.linea}
                </p>
                <p
                  className={`mt-4 border-t pt-3 text-[13px] ${
                    destacado ? "border-white/25 text-white/70" : "border-[color:var(--line)] text-[color:var(--muted)]"
                  }`}
                >
                  {m.meta}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════════════════ GALERÍA DE OUTPUTS ══════════════════ */}
      <section id="outputs" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Outputs"
          titulo="Lo que Dona produce"
          sub={
            <>
              No solo features: <strong>trabajo real y entregable.</strong> Estos son
              ejemplos de lo que sale del loop.
            </>
          }
        />
        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {OUTPUTS.map((o, i) => {
            const Icon = o.icon;
            return (
              <div
                key={o.titulo}
                data-reveal
                style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                className="surface-card overflow-hidden p-0"
              >
                {/* cabecera de "documento" con tinte de marca contenido */}
                <div className="relative flex h-28 items-center justify-center border-b border-[color:var(--line)] bg-[color:var(--fill)]">
                  <div
                    className="pointer-events-none absolute inset-0 opacity-70"
                    style={{
                      background:
                        "radial-gradient(60% 90% at 30% 20%, rgba(99,102,241,0.16), transparent 70%), radial-gradient(50% 80% at 80% 70%, rgba(196,181,253,0.2), transparent 72%)",
                    }}
                    aria-hidden
                  />
                  <span className="relative grid h-11 w-11 place-items-center rounded-xl bg-white text-[color:var(--brand-ink)] shadow-sm">
                    <Icon className="h-5 w-5" />
                  </span>
                </div>
                <div className="p-6">
                  <h3 className="text-[15px] font-medium text-[color:var(--ink)]">{o.titulo}</h3>
                  <p className="lead mt-2 text-[16px] leading-relaxed">{o.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════════════════ CONTROL HUMANO Y CONFIANZA (obligatoria) ══════════════════ */}
      <section id="control" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Control humano y confianza"
          titulo="Dona no ejecuta a ciegas"
          sub={
            <>
              Toda acción con costo o efecto irreversible pasa por{" "}
              <strong>preparación y confirmación.</strong> Tú mandas; Dona deja el rastro.
            </>
          }
        />
        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {CONTROLES.map((c, i) => {
            const Icon = c.icon;
            return (
              <div
                key={c.titulo}
                data-reveal
                style={{ "--reveal-delay": `${i * 60}ms` } as React.CSSProperties}
                className="surface-card p-8"
              >
                <span className="icon-badge h-12 w-12">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-[15px] font-medium text-[color:var(--ink)]">{c.titulo}</h3>
                <p className="lead mt-2 text-[16px] leading-relaxed">{c.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════════════════ CASOS POR SEGMENTO ══════════════════ */}
      <section id="casos" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Casos"
          titulo={"Un resultado concreto\npara cada quien"}
          sub={
            <>
              No etiquetas: <strong>resultados.</strong> Así se ve Dona según desde dónde
              trabajes.
            </>
          }
        />
        <div className="mt-16 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CASOS.map((c, i) => {
            const Icon = c.icon;
            return (
              <div
                key={c.segmento}
                data-reveal
                style={{ "--reveal-delay": `${i * 50}ms` } as React.CSSProperties}
                className="surface-card flex flex-col p-8"
              >
                <span className="icon-badge h-11 w-11">
                  <Icon className="h-[18px] w-[18px]" />
                </span>
                <h3 className="mt-4 text-[15px] font-medium text-[color:var(--ink)]">{c.segmento}</h3>
                <p className="lead mt-2 text-[16px] leading-relaxed">{c.resultado}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ══════════════════ PRICING ══════════════════ */}
      <section id="pricing" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead
          eyebrow="Precios"
          titulo={"Simple\ny transparente"}
          sub={
            <>
              Elige el plan que se ajuste a tu negocio. <strong>Cancela cuando quieras,
              sin permanencia.</strong>
            </>
          }
        />
        <div className="mx-auto mt-16 grid max-w-4xl gap-5 md:grid-cols-3">
          {PRICING.map((p) => (
            <div
              key={p.plan}
              className={`${p.destacado ? "card-gradient" : "surface-card"} flex flex-col p-7`}
            >
              {p.destacado && (
                <span className="hero-mono mb-3 inline-flex w-fit items-center rounded-full bg-white/20 px-2.5 py-1 text-[10px] uppercase tracking-[0.14em] text-white">
                  Recomendado
                </span>
              )}
              <p className={p.destacado ? "hero-mono text-[12px] uppercase tracking-[0.16em] text-white/80" : "eyebrow"}>
                {p.nombre}
              </p>
              <div className="mt-3 flex items-end gap-1">
                <span className={`text-5xl font-medium tracking-tight ${p.destacado ? "text-white" : "text-[color:var(--ink)]"}`}>
                  {p.precio}
                </span>
                <span className={`mb-1.5 ${p.destacado ? "text-white/75" : "text-[color:var(--muted)]"}`}>{p.periodo}</span>
              </div>
              <ul className="mt-6 flex-1 space-y-3">
                {p.features.map((f) => (
                  <li
                    key={f}
                    className={`flex items-start gap-2 text-[14px] ${p.destacado ? "text-white/90" : "text-[color:var(--ink-2)]"}`}
                  >
                    <Check
                      className="mt-0.5 h-4 w-4 shrink-0"
                      style={{ color: p.destacado ? "#fff" : "var(--brand-ink)" }}
                    />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => handleCheckout(p.plan)}
                disabled={checkoutLoading === p.plan}
                className={`${p.destacado ? "btn-inverse" : "btn-primary"} mt-8 inline-flex w-full cursor-pointer items-center justify-center rounded-full px-5 py-3 text-sm font-medium`}
              >
                {checkoutLoading === p.plan ? "Redirigiendo…" : "Empezar ahora"}
              </button>
            </div>
          ))}

          {/* Enterprise — próximamente, sin checkout */}
          <div className="surface-fill flex flex-col p-7">
            <div className="flex items-center gap-2">
              <p className="eyebrow">Enterprise</p>
              <span className="hero-mono rounded-full bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[color:var(--muted)]">
                Próximamente
              </span>
            </div>
            <div className="mt-3 flex items-end gap-1">
              <span className="text-4xl font-medium tracking-tight text-[color:var(--ink)]">A medida</span>
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
      </section>

      {/* ══════════════════ CTA FINAL ══════════════════ */}
      <section className="relative z-10 overflow-hidden">
        <div className="relative mx-auto max-w-3xl px-6 py-24 text-center md:py-32">
          <div className="aurora aurora--cta" aria-hidden />
          <h2 className="relative mx-auto max-w-2xl text-4xl font-medium leading-tight tracking-tight text-[color:var(--ink)] sm:text-5xl md:text-6xl">
            Empieza con una idea. <span className="text-aurora">Dona la convierte en ejecución.</span>
          </h2>
          <p className="lead relative mx-auto mt-6 max-w-xl text-lg leading-relaxed">
            Del primer mensaje al primer resultado — con <strong>permisos, costo y
            medición</strong> desde el principio.
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
      <section id="faq" className="relative z-10 mx-auto max-w-7xl px-6 py-20 md:py-28">
        <SectionHead eyebrow="FAQ" titulo="Preguntas frecuentes" />
        <div className="mx-auto mt-12 max-w-3xl space-y-3">
          {FAQ.map((f) => (
            <FaqItem key={f.q} q={f.q} a={f.a} />
          ))}
        </div>
      </section>

      {/* ══════════════════ FOOTER ══════════════════ */}
      <footer className="relative z-10 border-t border-[color:var(--line)] bg-white">
        <div className="mx-auto max-w-7xl px-6 py-14">
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

          {/* Ficha editorial (patrón case-study: metadata con hairline) */}
          <dl className="mt-12 grid max-w-3xl gap-x-16 gap-y-7 sm:grid-cols-2">
            <div className="meta-item">
              <dt>Producto</dt>
              <dd>Dona</dd>
            </div>
            <div className="meta-item">
              <dt>Categoría</dt>
              <dd>Plataforma-agente de negocio</dd>
            </div>
            <div className="meta-item">
              <dt>Canales de entrada</dt>
              <dd>WhatsApp · web · voz</dd>
            </div>
            <div className="meta-item">
              <dt>Año</dt>
              <dd>{new Date().getFullYear()}</dd>
            </div>
          </dl>

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
