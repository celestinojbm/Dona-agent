"use client";

import { Fragment, useState, useEffect, useLayoutEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  Brain,
  Sparkles,
  MessageSquare,
  Calendar,
  Mail,
  CheckCircle2,
  ChevronDown,
  ArrowRight,
  Shield,
  Globe,
  Menu,
  X,
  Mic,
  Image,
  DollarSign,
  Compass,
  Languages,
} from "lucide-react";
import { useCinematicMotion } from "./useCinematicMotion";

/* ════════════════════════════════════════════════════════════
   i18n — All page text in ES and EN
   ════════════════════════════════════════════════════════════ */

const i18n = {
  ES: {
    nav: {
      capabilities: "Capacidades",
      how: "Como funciona",
      pricing: "Precios",
      faq: "FAQ",
      login: "Login",
      start: "Comenzar",
    },
    hero: {
      line1: "Convierte tu intencion",
      line3: "con control total.",
      subtitle:
        "Dona es tu plataforma-agente de negocio: convierte situaciones y objetivos en activos, workflows, documentos, campañas y acciones reales — con creditos, permisos, trazabilidad y medicion. Le escribes y prepara, confirma y ejecuta contigo.",
      cta: "Empezar en WhatsApp",
      secondary: "Ver capacidades",
      stats: [
        { value: "+100", label: "capacidades de alta conversion integradas" },
        { value: "100%", label: "con permiso y trazabilidad" },
        { value: "24/7", label: "disponible siempre" },
      ],
    },
    rotating: [
      "en workflows",
      "en campañas",
      "en documentos",
      "en automatizaciones",
      "en acciones reales",
    ],
    painLabel: "El problema que Dona resuelve",
    painStats: [
      { num: 14, prefix: "", suffix: "h", sub: "", label: "a la semana perdidas cambiando entre apps, segun estudios de productividad" },
      { num: 24, prefix: "$", suffix: "K", sub: "", label: "al a\u00f1o en productividad desperdiciada por emprendedor, segun industria" },
      { num: 73, prefix: "", suffix: "%", sub: "", label: "de tareas criticas se pierden sin un sistema central" },
      { num: 4, prefix: "", suffix: "x", sub: "", label: "mas iniciativas en marcha cuando hay un sistema centralizado de seguimiento" },
    ],
    how: {
      label: "Como funciona",
      title: "De cero a productivo en 2 minutos",
      subtitle: "Sin descargas. Sin configuraciones complicadas. Solo WhatsApp.",
      steps: [
        { step: "01", title: "Agrega a Dona", desc: "Guardas el numero de Dona en tus contactos y le envias un mensaje. Dona se presenta y te guia en la configuracion inicial de 60 segundos." },
        { step: "02", title: "Conecta tus herramientas", desc: "Dona se integra con Gmail, Google Calendar y tus apps favoritas. Un link seguro, un clic, y todo queda sincronizado." },
        { step: "03", title: "Empieza a delegar", desc: "Enviare tu correo, agendare tu cita, recordare esa tarea. Habla con Dona como le hablarias a tu mejor asistente." },
      ],
    },
    capabilities: {
      label: "Capacidades",
      title: "Todo lo que Dona puede hacer",
      subtitle: "+100 capacidades de alta conversion integradas en un solo chat. Sin apps extra, sin friccion, sin curva de aprendizaje.",
      items: [
        { icon: "Brain", title: "Memoria inteligente", desc: "Dona retiene cada contacto, decision, idea y detalle que le compartas. No importa si fue hace dos dias o hace dos meses — preguntale y lo recuerda al instante. Es como tener un segundo cerebro que nunca olvida nada, organizado y listo para cuando lo necesites." },
        { icon: "Sparkles", title: "Simulacion de escenarios", desc: "Antes de tomar una decision importante, pidele a Dona que analice el impacto. Subir precios, contratar a alguien, cambiar de proveedor — Dona evalua los numeros, los riesgos y te da una recomendacion clara. Muchas veces el problema no es falta de informacion, sino falta de direccion." },
        { icon: "Mail", title: "Correo y calendario", desc: "Dona lee tus correos, te resume lo importante y puede responder por ti. Tambien maneja tu calendario: agenda reuniones, te avisa de conflictos y te prepara para lo que viene. Todo sin abrir Gmail ni Google Calendar — directamente desde tu chat. Dona nunca envia mensajes ni correos sin tu autorizacion explicita." },
        { icon: "Calendar", title: "Agenda y recordatorios", desc: "Crea recordatorios, da seguimiento a tus pendientes y recibe alertas antes de que algo se te pase. Dona no solo guarda la tarea — entiende la urgencia, te prioriza lo importante y te empuja cuando algo lleva tiempo sin moverse." },
        { icon: "Mic", title: "Comandos de voz", desc: "Envia una nota de voz y Dona la transcribe, interpreta y ejecuta. Pedile que agende algo, que anote una idea o que busque informacion — todo con tu voz, sin escribir ni un caracter. Perfecto para cuando estas manejando o en medio de algo." },
        { icon: "MessageSquare", title: "Respuestas automaticas de WhatsApp", desc: "Dona responde los mensajes de WhatsApp de tu negocio de forma inteligente y en tu nombre. Entiende el contexto de cada conversacion, responde con el tono de tu marca y escala a ti solo cuando es necesario. Tus clientes siempre atendidos, incluso a las 3am." },
        { icon: "Image", title: "Comprende imagenes y documentos", desc: "Mandale una foto de una factura, un recibo o cualquier documento y Dona lo lee, extrae los datos importantes y los guarda automaticamente. Nada de transcribir numeros a mano ni perder papeles. Le tomas foto y listo." },
        { icon: "DollarSign", title: "Seguimiento de gastos y finanzas", desc: "Registra gastos, ingresos y movimientos desde el chat. Dona los categoriza, te muestra tendencias y te alerta si algo se sale de lo normal. No reemplaza a tu contador, pero te da una radiografia diaria de tu dinero sin abrir una hoja de calculo." },
        { icon: "Compass", title: "Respuestas basadas en contexto", desc: "Dona no da respuestas genericas — entiende tu negocio, tu historial y tus preferencias. Cada respuesta esta informada por todo lo que le has compartido antes. Es como hablar con alguien que de verdad conoce tu operacion y sabe lo que necesitas escuchar." },
      ],
    },
    whyDona: {
      label: "Por que Dona",
      title: "Construida para emprendedores",
      cards: [
        { icon: "Brain", title: "Memoria que aprende", desc: "No repites informacion. Dona retiene cada dato, contacto y decision. Preguntale lo que sea, cuando sea." },
        { icon: "Sparkles", title: "Escenarios simulados", desc: "Subir precios? Contratar? Dona analiza el impacto financiero antes de que tomes una decision costosa." },
        { icon: "Shield", title: "Privacidad responsable", desc: "TLS en todas las comunicaciones y tokens OAuth cifrados en reposo. No entrenamos modelos con tus datos. Trabajamos con un conjunto acotado de proveedores listados en nuestra politica de privacidad." },
        { icon: "Globe", title: "Hecho para hispanos en USA", desc: "Entiende espanol, ingles y spanglish. Disenada para la realidad del emprendedor latino que hace negocios en dos idiomas." },
      ],
    },
    testimonials: {
      label: "Usuarios beta",
      title: "Lo que dicen los primeros usuarios",
    },
    pricing: {
      label: "Precios",
      title: "Simple y transparente",
      subtitle: "Elige el plan que se ajuste a tu negocio. Sin sorpresas.",
      cancel: "Cancela cuando quieras. Sin permanencia.",
      earlyAccess: "Premium",
      pro: "Pro",
      enterprise: "Enterprise",
      comingSoon: "Proximamente",
      startNow: "Comenzar ahora",
      earlyFeatures: ["Correo y calendario", "Gestion de tareas", "Memoria inteligente", "Simulacion de escenarios", "Notas de voz", "Soporte prioritario"],
      proFeatures: ["Todo del plan anterior", "Integraciones avanzadas", "Multi-negocio", "API personalizada", "Automatizaciones", "Analisis y reportes"],
      enterpriseFeatures: ["Todo del plan Pro", "Equipo ilimitado", "SLA garantizado", "Onboarding dedicado", "Integraciones custom", "Soporte 24/7"],
    },
    cta: {
      title: "Tu negocio merece un asistente 24/7",
      subtitle: "Dona maneja tu correo, tu agenda, tus finanzas y tus mensajes de WhatsApp — todo desde un solo chat, para que tu te enfoques en lo que importa.",
      button: "Elige tu plan",
    },
    faq: {
      label: "FAQ",
      title: "Preguntas frecuentes",
      items: [
        { q: "Dona puede leer mis correos?", a: "Si. Dona se conecta a Gmail y Outlook para leer, resumir y responder correos. Tu apruebas cada accion antes de que se ejecute." },
        { q: "Es seguro compartir informacion de mi negocio?", a: "Usamos TLS en todas las comunicaciones y ciframos en reposo los datos sensibles (tokens OAuth, credenciales). No entrenamos modelos con tu informacion. Para operar el servicio trabajamos con un conjunto acotado de proveedores tecnicos (LLMs, infraestructura, mensajeria) listados publicamente en nuestra politica de privacidad." },
        { q: "Funciona en espanol e ingles?", a: "Dona entiende y responde en ambos idiomas. Puedes mezclar espanol e ingles en la misma conversacion sin problema." },
        { q: "Necesito instalar una app?", a: "No. Dona funciona 100% dentro de WhatsApp. Solo necesitas agregar el numero de Dona a tus contactos y empezar a escribir." },
        { q: "Puedo cancelar en cualquier momento?", a: "Si. No hay contratos ni permanencia. Cancelas cuando quieras desde tu cuenta, sin preguntas ni penalizaciones." },
      ],
    },
    footer: {
      tagline: "Plataforma-agente de negocio y ejecucion controlada",
      terms: "Terminos y condiciones",
      privacy: "Politica de privacidad",
      support: "Soporte",
      disclaimer: "Dona actua como asistente inteligente para tu negocio. Puede responder mensajes de WhatsApp, procesar imagenes como facturas y gestionar tu agenda. El uso del servicio implica la aceptacion de nuestros terminos.",
      copy: "Todos los derechos reservados.",
    },
  },
  EN: {
    nav: {
      capabilities: "Features",
      how: "How it works",
      pricing: "Pricing",
      faq: "FAQ",
      login: "Login",
      start: "Get started",
    },
    hero: {
      line1: "Turn your intent",
      line3: "with full control.",
      subtitle:
        "Dona is your business platform-agent: it turns situations and goals into assets, workflows, documents, campaigns and real actions — with credits, permissions, traceability and measurement. You message it and it prepares, confirms and executes with you.",
      cta: "Start in WhatsApp",
      secondary: "See features",
      stats: [
        { value: "+100", label: "high-conversion features built in" },
        { value: "100%", label: "with permission and traceability" },
        { value: "24/7", label: "always available" },
      ],
    },
    rotating: [
      "into workflows",
      "into campaigns",
      "into documents",
      "into automations",
      "into real actions",
    ],
    painLabel: "The problem Dona solves",
    painStats: [
      { num: 14, prefix: "", suffix: "h", sub: "", label: "per week lost switching between apps, according to productivity research" },
      { num: 24, prefix: "$", suffix: "K", sub: "", label: "per year in wasted productivity per entrepreneur, industry estimates" },
      { num: 73, prefix: "", suffix: "%", sub: "", label: "of critical tasks are lost without a central system" },
      { num: 4, prefix: "", suffix: "x", sub: "", label: "more initiatives in motion when tracked from a single system" },
    ],
    how: {
      label: "How it works",
      title: "Zero to productive in 2 minutes",
      subtitle: "No downloads. No complex setup. Just WhatsApp.",
      steps: [
        { step: "01", title: "Add Dona", desc: "Save Dona's number in your contacts and send a message. Dona introduces itself and guides you through a 60-second setup." },
        { step: "02", title: "Connect your tools", desc: "Dona integrates with Gmail, Google Calendar and your favorite apps. One secure link, one click, and everything is synced." },
        { step: "03", title: "Start delegating", desc: "Send your email, schedule your meeting, remember that task. Talk to Dona like you would to your best assistant." },
      ],
    },
    capabilities: {
      label: "Features",
      title: "Everything Dona can do",
      subtitle: "+100 high-conversion features built into a single chat. No extra apps, no friction, no learning curve.",
      items: [
        { icon: "Brain", title: "Smart memory", desc: "Dona remembers every contact, decision, idea and detail you share. It doesn't matter if it was two days or two months ago — ask and it recalls instantly. Like a second brain that never forgets, organized and ready when you need it." },
        { icon: "Sparkles", title: "Scenario simulation", desc: "Before making a big decision, ask Dona to analyze the impact. Raising prices, hiring someone, switching suppliers — Dona evaluates the numbers, the risks and gives you a clear recommendation. Often the problem isn't lack of information, but lack of direction." },
        { icon: "Mail", title: "Email and calendar", desc: "Dona reads your emails, summarizes what matters and can reply for you. It also manages your calendar: schedules meetings, warns about conflicts and prepares you for what's next. All without opening Gmail or Google Calendar — straight from your chat. Dona never sends messages or emails without your explicit authorization." },
        { icon: "Calendar", title: "Agenda and reminders", desc: "Create reminders, track your to-dos and get alerts before something slips. Dona doesn't just save tasks — it understands urgency, prioritizes what matters and nudges you when something has been sitting too long." },
        { icon: "Mic", title: "Voice commands", desc: "Send a voice note and Dona transcribes, interprets and executes it. Ask it to schedule something, jot down an idea or look up information — all with your voice, without typing a single character. Perfect when you're driving or in the middle of something." },
        { icon: "MessageSquare", title: "Auto WhatsApp replies", desc: "Dona replies to your business WhatsApp messages intelligently and on your behalf. It understands the context of each conversation, responds in your brand's tone and escalates to you only when needed. Your customers always attended, even at 3am." },
        { icon: "Image", title: "Image and document understanding", desc: "Send a photo of an invoice, receipt or any document and Dona reads it, extracts the important data and saves it automatically. No more transcribing numbers by hand or losing papers. Snap a photo and done." },
        { icon: "DollarSign", title: "Expense and finance tracking", desc: "Log expenses, income and transactions from the chat. Dona categorizes them, shows trends and alerts you if something looks off. It doesn't replace your accountant, but gives you a daily snapshot of your money without opening a spreadsheet." },
        { icon: "Compass", title: "Context-based answers", desc: "Dona doesn't give generic replies — it understands your business, your history and your preferences. Every answer is informed by everything you've shared before. Like talking to someone who truly knows your operation and knows what you need to hear." },
      ],
    },
    whyDona: {
      label: "Why Dona",
      title: "Built for entrepreneurs",
      cards: [
        { icon: "Brain", title: "Memory that learns", desc: "No repeating yourself. Dona retains every piece of data, contact and decision. Ask anything, anytime." },
        { icon: "Sparkles", title: "Simulated scenarios", desc: "Raise prices? Hire? Dona analyzes the financial impact before you make an expensive decision." },
        { icon: "Shield", title: "Responsible privacy", desc: "TLS for all communications and OAuth tokens encrypted at rest. We don't train models on your data. We work with a limited set of providers listed in our privacy policy." },
        { icon: "Globe", title: "Made for Hispanics in the US", desc: "Understands Spanish, English and Spanglish. Designed for the reality of the Latino entrepreneur doing business in two languages." },
      ],
    },
    testimonials: {
      label: "Beta users",
      title: "What early users are saying",
    },
    pricing: {
      label: "Pricing",
      title: "Simple and transparent",
      subtitle: "Choose the plan that fits your business. No surprises.",
      cancel: "Cancel anytime. No lock-in.",
      earlyAccess: "Premium",
      pro: "Pro",
      enterprise: "Enterprise",
      comingSoon: "Coming soon",
      startNow: "Get started",
      earlyFeatures: ["Email and calendar", "Task management", "Smart memory", "Scenario simulation", "Voice notes", "Priority support"],
      proFeatures: ["Everything in previous plan", "Advanced integrations", "Multi-business", "Custom API", "Automations", "Analytics and reports"],
      enterpriseFeatures: ["Everything in Pro", "Unlimited team", "Guaranteed SLA", "Dedicated onboarding", "Custom integrations", "24/7 support"],
    },
    cta: {
      title: "Your business deserves a 24/7 assistant",
      subtitle: "Dona handles your email, calendar, finances and WhatsApp messages — all from one chat, so you can focus on what matters.",
      button: "Choose your plan",
    },
    faq: {
      label: "FAQ",
      title: "Frequently asked questions",
      items: [
        { q: "Can Dona read my emails?", a: "Yes. Dona connects to Gmail and Outlook to read, summarize and reply to emails. You approve every action before it's executed." },
        { q: "Is it safe to share my business information?", a: "We use TLS for all communications and encrypt sensitive data at rest (OAuth tokens, credentials). We don't train models on your information. To run the service we work with a limited set of technical providers (LLMs, infrastructure, messaging) listed publicly in our privacy policy." },
        { q: "Does it work in Spanish and English?", a: "Dona understands and replies in both languages. You can mix Spanish and English in the same conversation seamlessly." },
        { q: "Do I need to install an app?", a: "No. Dona works 100% inside WhatsApp. Just save Dona's number and start chatting." },
        { q: "Can I cancel anytime?", a: "Yes. No contracts, no lock-in. Cancel whenever you want from your account — no questions asked." },
      ],
    },
    footer: {
      tagline: "Business platform-agent for controlled execution",
      terms: "Terms and conditions",
      privacy: "Privacy policy",
      support: "Support",
      disclaimer: "Dona acts as an intelligent assistant for your business. It can reply to WhatsApp messages, process images such as invoices, and manage your calendar. Using the service implies acceptance of our terms.",
      copy: "All rights reserved.",
    },
  },
} as const;

type Lang = keyof typeof i18n;

/* Testimonials (not translated — real names stay) */
const testimonials = [
  { name: "Carlos Montoya", role: "Fundador, importadora en Miami", text: "Dona me ahorra 2 horas al dia. Ya no reviso correos uno por uno — me manda un resumen y responde por mi." },
  { name: "Valeria Restrepo", role: "Consultora de marketing digital", text: "La simulacion de escenarios es otra cosa. Le pregunte si debia subir tarifas y me dio un analisis que mi contador no me habia dado." },
  { name: "Diego Fuentes", role: "E-commerce, envios a LATAM", text: "Lo mejor es la memoria. Le digo algo una vez y nunca lo olvida. Es como tener un asistente que realmente escucha." },
  { name: "Andrea Lopez", role: "Duena de restaurante en Houston", text: "Le mando fotos de facturas y me las organiza sola. Antes perdia una hora al dia en eso. Ahora ni lo pienso." },
  { name: "Marco Herrera", role: "Agente de bienes raices", text: "Dona responde a mis clientes de WhatsApp cuando estoy en showings. Nadie espera y yo no pierdo oportunidades." },
  { name: "Sofia Chen", role: "Freelancer de diseno en LA", text: "Es como tener un asistente que entiende mi negocio. Le pregunto cualquier cosa y siempre tiene el contexto correcto." },
];

/* Icon map for capabilities */
const iconMap = { Brain, Sparkles, Mail, Calendar, Mic, MessageSquare, Image, DollarSign, Compass, Shield, Globe } as const;

/* ════════════════════════════════════════════════════════════
   ISOLATED COMPONENTS
   ════════════════════════════════════════════════════════════ */

function Counter({ target, suffix = "", prefix = "" }: { target: number; suffix?: string; prefix?: string }) {
  // El numero se renderiza como `target` por defecto (SSR / sin JS / reduced-motion):
  // sin flash de 0. useCinematicMotion anima 0→target al entrar en vista (data-countup).
  return (
    <span className="tabular-nums font-mono">
      {prefix}<span data-countup={target}>{target}</span>{suffix}
    </span>
  );
}

function FadeIn({ children, delay = 0, direction = "up", className = "" }: { children: React.ReactNode; delay?: number; direction?: "up" | "down" | "left" | "right"; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  // Hide before first paint (no flash). Skipped on bfcache restore since DOM already has data-fade="visible".
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || el.getAttribute("data-fade") === "visible") return;
    el.setAttribute("data-fade", "pending");
    el.style.setProperty("--fade-delay", `${delay}s`);
    el.style.setProperty("--fade-dir", direction);
  }, [delay, direction]);

  // Observe intersection, then reveal once
  useEffect(() => {
    const el = ref.current;
    if (!el || el.getAttribute("data-fade") === "visible") return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.setAttribute("data-fade", "visible");
          observer.disconnect();
        }
      },
      { rootMargin: "-80px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return <div ref={ref} className={className}>{children}</div>;
}

function KineticText({ text, startIndex = 0 }: { text: string; startIndex?: number }) {
  // Parte el texto en palabras envueltas en `.kinetic-word` para que el titular
  // [data-kinetic] las revele palabra-por-palabra (estilo LTX). `--ki` lleva el
  // indice global de la palabra (continuo entre lineas via `startIndex`) para
  // escalonar el delay. El espacio entre palabras es un nodo de texto normal para
  // que el titular siga partiendo lineas en pantallas chicas. Sin JS o con
  // reduced-motion las palabras quedan visibles (ver globals.css).
  const words = text.split(" ");
  return (
    <>
      {words.map((w, i) => (
        <Fragment key={i}>
          {i > 0 && " "}
          <span className="kinetic-word" style={{ "--ki": startIndex + i } as React.CSSProperties}>
            {w}
          </span>
        </Fragment>
      ))}
    </>
  );
}

function RotatingText({ words }: { words: readonly string[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIndex((i) => (i + 1) % words.length), 2800);
    return () => clearInterval(t);
  }, [words.length]);
  return (
    <span className="inline-block relative h-[1.2em] overflow-hidden align-bottom w-full">
      <AnimatePresence mode="wait">
        <motion.span
          key={words[index]}
          initial={{ y: 40, opacity: 0, filter: "blur(10px)" }}
          animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
          exit={{ y: -40, opacity: 0, filter: "blur(10px)" }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="absolute inset-x-0 text-gradient whitespace-nowrap"
        >
          {words[index]}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

function TestimonialCarousel() {
  const doubled = [...testimonials, ...testimonials];
  return (
    <div className="overflow-hidden">
      <div className="carousel-track flex gap-6 w-max">
        {doubled.map((t, i) => (
          <div key={i} className="glass-card rounded-2xl p-8 flex flex-col w-[340px] shrink-0">
            <p className="text-sm text-white/45 leading-relaxed flex-1 mb-6 italic font-light">&ldquo;{t.text}&rdquo;</p>
            <div>
              <p className="text-sm font-normal text-white/70">{t.name}</p>
              <p className="text-xs text-white/25 font-light">{t.role}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FAQSection({ items }: { items: readonly { q: string; a: string }[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-3 max-w-2xl mx-auto">
      {items.map((item, i) => (
        <div key={i} className="glass-card rounded-xl overflow-hidden">
          <button onClick={() => setOpen(open === i ? null : i)} className="w-full flex items-center justify-between px-6 py-5 text-left text-white/80 hover:text-white transition-colors cursor-pointer">
            <span className="font-light text-sm md:text-base pr-4">{item.q}</span>
            <ChevronDown className={`w-5 h-5 shrink-0 transition-transform duration-300 ${open === i ? "rotate-180" : ""}`} />
          </button>
          <AnimatePresence>
            {open === i && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }}>
                <div className="px-6 pb-5 text-sm text-white/40 leading-relaxed font-light">{item.a}</div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   MAIN PAGE
   ═══════════════════════════════════════════════════════ */

export default function Home() {
  const [lang, setLang] = useState<Lang>("ES");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  // Nav cinematica (iter 7): la barra se "despega" del hero al hacer scroll
  // (backdrop + hairline) y el scroll-spy marca la seccion activa.
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState<string>("");
  const reduceMotion = useReducedMotion();
  const t = i18n[lang];

  // Capa de movimiento cinematografico (GSAP): parallax del video, count-up real,
  // spotlight en cards y hover magnetico en los CTAs.
  useCinematicMotion();

  // Nav scrolled state (iter 7): traslucido + borde al pasar el primer scroll.
  // Cerca del tope no hay seccion activa (estamos en el hero). Solo togglea
  // clases/estado (opacidad/color), nada de movimiento desorientante.
  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY;
      setScrolled(y > 24);
      if (y < 200) setActiveSection("");
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Scroll-spy (iter 7): observa las secciones ancladas del nav y marca activa la
  // que cruza una banda cerca del centro del viewport. Limpia el observer al
  // desmontar.
  useEffect(() => {
    const ids = ["how", "capabilities", "pricing", "faq"];
    const sections = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActiveSection(entry.target.id);
        }
      },
      { rootMargin: "-40% 0px -55% 0px" }
    );
    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  // Items del nav (desktop): orden visual. El scroll-spy usa el id de cada seccion.
  const navItems: { id: string; label: string }[] = [
    { id: "capabilities", label: t.nav.capabilities },
    { id: "how", label: t.nav.how },
    { id: "pricing", label: t.nav.pricing },
    { id: "faq", label: t.nav.faq },
  ];


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
        alert(data.error || "Error creating checkout session");
        setCheckoutLoading(null);
      }
    } catch {
      alert("Connection error. Please try again.");
      setCheckoutLoading(null);
    }
  }, []);

  return (
    <>
      {/* ── Nav — transparent, se despega del hero al hacer scroll ── */}
      <nav className={`fixed top-0 left-0 right-0 z-50 nav-bar ${scrolled ? "nav-bar-scrolled" : ""}`}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <a href="#" className="text-4xl font-normal tracking-tight text-white nav-link">
            Dona
          </a>

          {/* Desktop — scroll-spy: la seccion activa se resalta y el indicador
              se desliza entre items (layout animation; estatico con reduced-motion). */}
          <div className="hidden md:flex items-center gap-7 text-sm text-white/40 font-light">
            {navItems.map((item) => {
              const active = activeSection === item.id;
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  aria-current={active ? "true" : undefined}
                  className={`nav-link relative ${active ? "nav-link-active" : ""}`}
                >
                  {item.label}
                  {active &&
                    (reduceMotion ? (
                      <span className="nav-indicator" />
                    ) : (
                      <motion.span
                        layoutId="nav-indicator"
                        className="nav-indicator"
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    ))}
                </a>
              );
            })}
            <button onClick={() => setLang(lang === "ES" ? "EN" : "ES")} className="flex items-center gap-1.5 nav-link cursor-pointer">
              <Languages className="w-4 h-4" />
              <span className="text-xs font-mono">{lang}</span>
            </button>
            <a href="/login" className="nav-link text-white/40">{t.nav.login}</a>
            <a href="#pricing" data-magnetic className="btn-primary px-5 py-2 rounded-full text-sm">{t.nav.start}</a>
          </div>

          {/* Mobile toggle */}
          <button className="md:hidden text-white/50" onClick={() => setMobileMenu(!mobileMenu)}>
            {mobileMenu ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        <AnimatePresence>
          {mobileMenu && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="md:hidden overflow-hidden backdrop-blur-xl bg-black/70 border-b border-white/[0.06]">
              <div className="flex flex-col gap-4 px-6 py-6 text-sm text-white/50 font-light">
                <a href="#capabilities" onClick={() => setMobileMenu(false)} className="nav-link">{t.nav.capabilities}</a>
                <a href="#how" onClick={() => setMobileMenu(false)} className="nav-link">{t.nav.how}</a>
                <a href="#pricing" onClick={() => setMobileMenu(false)} className="nav-link">{t.nav.pricing}</a>
                <a href="#faq" onClick={() => setMobileMenu(false)} className="nav-link">{t.nav.faq}</a>
                <button onClick={() => { setLang(lang === "ES" ? "EN" : "ES"); setMobileMenu(false); }} className="flex items-center gap-1.5 nav-link">
                  <Languages className="w-4 h-4" /><span className="text-xs font-mono">{lang}</span>
                </button>
                <a href="/login" onClick={() => setMobileMenu(false)} className="nav-link">{t.nav.login}</a>
                <a href="#pricing" onClick={() => setMobileMenu(false)} className="btn-primary px-5 py-2.5 rounded-full text-center text-sm">{t.nav.start}</a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ══════════════════════════════════════════════════════
          HERO
          ══════════════════════════════════════════════════════ */}
      <section className="relative z-[2] min-h-[100dvh] flex items-center justify-center pt-16">
        <div className="max-w-4xl mx-auto px-6 py-24 md:py-32 w-full text-center">
          {/* El titular hace su entrada cinematografica palabra-por-palabra
              (useCinematicMotion togglea [data-kinetic] pending→visible), no con
              el FadeIn de bloque. line3 continua el stagger de line1 via startIndex. */}
          <h1 data-kinetic className="text-5xl md:text-7xl lg:text-8xl font-normal leading-[1.1] tracking-tighter mb-8 text-white">
            <KineticText text={t.hero.line1} />
            <br />
            <RotatingText words={t.rotating} />
            <br />
            <span className="text-white/70 font-extralight">
              <KineticText text={t.hero.line3} startIndex={t.hero.line1.split(" ").length} />
            </span>
          </h1>

          <FadeIn delay={0.2}>
            <p className="text-lg md:text-xl text-white/50 max-w-xl mx-auto mb-10 leading-relaxed font-light">
              {t.hero.subtitle}
            </p>
          </FadeIn>

          <FadeIn delay={0.3}>
            <div className="flex flex-wrap gap-4 justify-center mb-14">
              <a href="#pricing" data-magnetic className="btn-primary px-8 py-4 rounded-full text-sm flex items-center gap-2 pulse-glow">
                {t.hero.cta}
                <ArrowRight className="w-4 h-4" />
              </a>
              <a href="#capabilities" data-magnetic className="btn-secondary px-8 py-4 rounded-full text-sm font-light">
                {t.hero.secondary}
              </a>
            </div>
          </FadeIn>

          <FadeIn delay={0.4}>
            <div className="flex gap-12 justify-center text-center">
              {t.hero.stats.map((stat, i) => (
                <div key={i}>
                  <div className="text-2xl font-normal text-white/80">{stat.value}</div>
                  <div className="text-[11px] text-white/45 mt-1 uppercase tracking-wider font-light">{stat.label}</div>
                </div>
              ))}
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          PAIN NUMBERS
          ══════════════════════════════════════════════════════ */}
      <section className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn>
            <p className="text-center text-xs uppercase tracking-[0.25em] text-white/25 mb-20 font-light">{t.painLabel}</p>
          </FadeIn>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-10 md:gap-16 text-center">
            {t.painStats.map((item, i) => (
              <FadeIn key={i} delay={i * 0.12}>
                <div className="text-6xl md:text-8xl font-extralight text-gradient-stat tracking-tighter leading-none">
                  <Counter target={item.num} suffix={item.suffix} prefix={item.prefix} />
                  {item.sub && <span className="text-lg md:text-xl font-light text-white/25">{item.sub}</span>}
                </div>
                <p className="mt-6 text-sm text-white/35 max-w-[240px] mx-auto leading-relaxed font-light">{item.label}</p>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ══════════════════════════════════════════════════════
          HOW IT WORKS
          ══════════════════════════════════════════════════════ */}
      <section id="how" className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs uppercase tracking-[0.25em] text-white/25 mb-4 text-center font-light">{t.how.label}</p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal text-center mb-6 tracking-tighter text-white">{t.how.title}</h2>
            <p className="text-center text-white/35 max-w-lg mx-auto mb-20 font-light">{t.how.subtitle}</p>
          </FadeIn>
          <div className="space-y-20 md:space-y-28">
            {t.how.steps.map((item, i) => (
              <FadeIn key={i} delay={0.1}>
                <div className="grid md:grid-cols-12 gap-8 items-start">
                  <div className="md:col-span-3"><div className="step-number">{item.step}</div></div>
                  <div className="md:col-span-9 md:pt-6">
                    <h3 className="text-2xl md:text-3xl font-normal mb-4 tracking-tight text-white">{item.title}</h3>
                    <p className="text-white/35 text-base md:text-lg leading-relaxed max-w-xl font-light">{item.desc}</p>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ══════════════════════════════════════════════════════
          CAPABILITIES
          ══════════════════════════════════════════════════════ */}
      <section id="capabilities" className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs uppercase tracking-[0.25em] text-white/25 mb-4 text-center font-light">{t.capabilities.label}</p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal text-center mb-4 tracking-tighter text-white">{t.capabilities.title}</h2>
            <p className="text-center text-white/35 max-w-xl mx-auto mb-20 font-light">{t.capabilities.subtitle}</p>
          </FadeIn>
          <div className="grid md:grid-cols-3 gap-6">
            {t.capabilities.items.map((cap, i) => {
              const Icon = iconMap[cap.icon as keyof typeof iconMap];
              return (
                <FadeIn key={i} delay={i * 0.06}>
                  <div data-spotlight className="glass-card rounded-2xl p-8 h-full group">
                    <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center mb-5 group-hover:border-[#7C3AED]/20 transition-colors">
                      <Icon className="w-6 h-6 text-white/40" />
                    </div>
                    <h3 className="text-lg font-normal mb-3 text-white">{cap.title}</h3>
                    <p className="text-sm text-white/35 leading-relaxed font-light">{cap.desc}</p>
                  </div>
                </FadeIn>
              );
            })}
          </div>
        </div>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ══════════════════════════════════════════════════════
          WHY DONA
          ══════════════════════════════════════════════════════ */}
      <section className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs uppercase tracking-[0.25em] text-white/25 mb-4 text-center font-light">{t.whyDona.label}</p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal text-center mb-20 tracking-tighter text-white">{t.whyDona.title}</h2>
          </FadeIn>
          <div className="grid md:grid-cols-2 gap-6">
            {t.whyDona.cards.map((card, i) => {
              const Icon = iconMap[card.icon as keyof typeof iconMap];
              return (
                <FadeIn key={i} delay={i * 0.1}>
                  <div data-spotlight className="glass-card rounded-2xl p-8 h-full group">
                    <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center mb-5 group-hover:border-[#7C3AED]/20 transition-colors">
                      <Icon className="w-6 h-6 text-white/40" />
                    </div>
                    <h3 className="text-lg font-normal mb-2 text-white">{card.title}</h3>
                    <p className="text-sm text-white/35 leading-relaxed font-light">{card.desc}</p>
                  </div>
                </FadeIn>
              );
            })}
          </div>
        </div>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ══════════════════════════════════════════════════════
          TESTIMONIALS — infinite carousel
          ══════════════════════════════════════════════════════ */}
      <section className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6 mb-16">
          <FadeIn>
            <p className="text-xs uppercase tracking-[0.25em] text-white/25 mb-4 text-center font-light">{t.testimonials.label}</p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal text-center mb-4 tracking-tighter text-white">{t.testimonials.title}</h2>
          </FadeIn>
        </div>
        <FadeIn><TestimonialCarousel /></FadeIn>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ══════════════════════════════════════════════════════
          PRICING
          ══════════════════════════════════════════════════════ */}
      <section id="pricing" className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs uppercase tracking-[0.25em] text-white/25 mb-4 text-center font-light">{t.pricing.label}</p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal text-center mb-4 tracking-tighter text-white">{t.pricing.title}</h2>
            <p className="text-center text-white/35 max-w-md mx-auto mb-20 font-light">{t.pricing.subtitle}</p>
          </FadeIn>

          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {/* Early Access */}
            <FadeIn delay={0}>
              <div className="glass-card rounded-2xl p-8 relative overflow-hidden">
                <p className="text-xs uppercase tracking-widest text-white/35 mb-2 font-light">{t.pricing.earlyAccess}</p>
                <div className="flex items-end gap-1 mb-6">
                  <span className="text-5xl font-light text-white">$20</span>
                  <span className="text-white/25 mb-1.5 font-light">/mes</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {t.pricing.earlyFeatures.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-white/45 font-light">
                      <CheckCircle2 className="w-4 h-4 text-white/30 shrink-0" />{f}
                    </li>
                  ))}
                </ul>
                <button onClick={() => handleCheckout("premium")} disabled={checkoutLoading === "premium"} className="btn-primary w-full py-3.5 rounded-full text-sm text-center block cursor-pointer disabled:opacity-50">
                  {checkoutLoading === "premium" ? "..." : t.pricing.startNow}
                </button>
              </div>
            </FadeIn>

            {/* Pro */}
            <FadeIn delay={0.1}>
              <div className="glass-card rounded-2xl p-8 relative overflow-hidden border-[#2563EB]/20">
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#2563EB] to-[#F97316]" />
                <p className="text-xs uppercase tracking-widest text-white/35 mb-2 font-light">{t.pricing.pro}</p>
                <div className="flex items-end gap-1 mb-6">
                  <span className="text-5xl font-light text-white">$40</span>
                  <span className="text-white/25 mb-1.5 font-light">/mes</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {t.pricing.proFeatures.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-white/45 font-light">
                      <CheckCircle2 className="w-4 h-4 text-white/30 shrink-0" />{f}
                    </li>
                  ))}
                </ul>
                <button onClick={() => handleCheckout("pro")} disabled={checkoutLoading === "pro"} className="btn-primary w-full py-3.5 rounded-full text-sm text-center block cursor-pointer disabled:opacity-50">
                  {checkoutLoading === "pro" ? "..." : t.pricing.startNow}
                </button>
              </div>
            </FadeIn>

            {/* Enterprise */}
            <FadeIn delay={0.2}>
              <div className="glass-card rounded-2xl p-8">
                <div className="flex items-center gap-2 mb-2">
                  <p className="text-xs uppercase tracking-widest text-white/35 font-light">{t.pricing.enterprise}</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-white/40 font-mono">{t.pricing.comingSoon}</span>
                </div>
                <div className="flex items-end gap-1 mb-6">
                  <span className="text-5xl font-light text-white">Custom</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {t.pricing.enterpriseFeatures.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-white/45 font-light">
                      <CheckCircle2 className="w-4 h-4 text-white/30 shrink-0" />{f}
                    </li>
                  ))}
                </ul>
                <button className="btn-secondary w-full py-3.5 rounded-full text-sm cursor-not-allowed opacity-50 font-light">{t.pricing.comingSoon}</button>
              </div>
            </FadeIn>
          </div>

          <FadeIn delay={0.3}>
            <div className="flex items-center justify-center gap-2 mt-10">
              <CheckCircle2 className="w-4 h-4 text-white/30" />
              <p className="text-white/30 text-sm font-light">{t.pricing.cancel}</p>
            </div>
          </FadeIn>
        </div>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ══════════════════════════════════════════════════════
          CTA — no email form, just button to pricing
          ══════════════════════════════════════════════════════ */}
      <section id="cta" className="relative z-[2] section-space">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <FadeIn>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal mb-6 tracking-tighter text-white">{t.cta.title}</h2>
            <p className="text-white/35 mb-12 max-w-md mx-auto text-lg font-light">{t.cta.subtitle}</p>
          </FadeIn>
          <FadeIn delay={0.15}>
            <a href="#pricing" data-magnetic className="btn-primary inline-flex items-center gap-2 px-10 py-4 rounded-full text-sm pulse-glow">
              {t.cta.button}
              <ArrowRight className="w-4 h-4" />
            </a>
          </FadeIn>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════
          FAQ
          ══════════════════════════════════════════════════════ */}
      <section id="faq" className="relative z-[2] section-space">
        <div className="max-w-7xl mx-auto px-6">
          <FadeIn>
            <p className="text-xs uppercase tracking-[0.25em] text-white/25 mb-4 text-center font-light">{t.faq.label}</p>
            <h2 className="text-3xl md:text-5xl lg:text-6xl font-normal text-center mb-20 tracking-tighter text-white">{t.faq.title}</h2>
          </FadeIn>
          <FadeIn delay={0.1}>
            <FAQSection items={t.faq.items} />
          </FadeIn>
        </div>
      </section>

      <div className="relative z-[2] divider-gradient" />

      {/* ── Footer ── */}
      <footer className="relative z-[2] py-16">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <span className="text-xl font-normal text-white">Dona</span>
              <span className="text-xs text-white/30 font-light">{t.footer.tagline}</span>
            </div>
            <div className="flex items-center gap-6 text-sm text-white/40 font-light">
              <a href="mailto:hola@usadona.com" className="nav-link">hola@usadona.com</a>
              <a href="https://instagram.com/usadonaapp" target="_blank" rel="noopener noreferrer" className="nav-link">Instagram</a>
              <a href="#" className="nav-link">X / Twitter</a>
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-white/[0.06]">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-6 text-xs text-white/30 font-light">
                <a href="/terminos-y-condiciones" className="nav-link">{t.footer.terms}</a>
                <a href="/politica-de-privacidad" className="nav-link">{t.footer.privacy}</a>
                <a href="/soporte" className="nav-link">{t.footer.support}</a>
              </div>
            </div>
            <p className="text-[11px] text-white/25 font-light mt-6 max-w-2xl mx-auto text-center leading-relaxed">
              {t.footer.disclaimer}
            </p>
          </div>

          <div className="mt-8 text-center text-xs text-white/20 font-light">
            &copy; {new Date().getFullYear()} Dona. {t.footer.copy}
          </div>
        </div>
      </footer>
    </>
  );
}
