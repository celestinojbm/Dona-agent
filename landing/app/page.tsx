"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence, useInView } from "framer-motion";
import {
  Brain,
  Sparkles,
  MessageSquare,
  Calendar,
  Mail,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ArrowRight,
  Zap,
  Shield,
  Globe,
  Clock,
  Send,
  Menu,
  X,
} from "lucide-react";

/* ─── Animated counter ─── */
function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const duration = 2000;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [isInView, target]);

  return (
    <span ref={ref} className="tabular-nums">
      {count}
      {suffix}
    </span>
  );
}

/* ─── Fade-in on scroll ─── */
function FadeIn({
  children,
  delay = 0,
  direction = "up",
  className = "",
}: {
  children: React.ReactNode;
  delay?: number;
  direction?: "up" | "down" | "left" | "right";
  className?: string;
}) {
  const offsets = {
    up: { y: 40, x: 0 },
    down: { y: -40, x: 0 },
    left: { x: 40, y: 0 },
    right: { x: -40, y: 0 },
  };
  return (
    <motion.div
      initial={{ opacity: 0, ...offsets[direction] }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ─── Rotating headline words ─── */
const rotatingWords = [
  "tu correo",
  "tu calendario",
  "tus tareas",
  "tu memoria",
  "tus escenarios",
];

function RotatingText() {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIndex((i) => (i + 1) % rotatingWords.length), 2800);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="inline-block relative h-[1.15em] overflow-hidden align-bottom min-w-[260px]">
      <AnimatePresence mode="wait">
        <motion.span
          key={rotatingWords[index]}
          initial={{ y: 30, opacity: 0, filter: "blur(8px)" }}
          animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
          exit={{ y: -30, opacity: 0, filter: "blur(8px)" }}
          transition={{ duration: 0.5 }}
          className="absolute left-0 text-gradient-main whitespace-nowrap"
        >
          {rotatingWords[index]}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

/* ─── Chat mockup ─── */
interface ChatMsg {
  role: "user" | "dona";
  text: string;
}

function ChatMockup({ messages }: { messages: ChatMsg[] }) {
  return (
    <div className="glass-card rounded-2xl p-5 max-w-sm w-full">
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-white/5">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4F46E5] to-[#7C3AED] flex items-center justify-center text-xs font-bold">
          D
        </div>
        <span className="text-sm font-medium text-white/80">Dona</span>
        <span className="ml-auto text-[10px] text-white/30">WhatsApp</span>
      </div>
      <div className="space-y-3">
        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.15 }}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-[#4F46E5]/30 text-white/90 rounded-br-md"
                  : "bg-white/[0.04] text-white/70 rounded-bl-md"
              }`}
            >
              {m.text}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

/* ─── Capabilities data ─── */
const capabilities = [
  {
    icon: Brain,
    title: "Memoria inteligente",
    desc: "Dona recuerda todo: contactos, decisiones, ideas. Pregúntale cualquier cosa que le hayas dicho antes.",
    messages: [
      { role: "user" as const, text: "¿Cuál era el nombre del proveedor de cajas?" },
      { role: "dona" as const, text: "PackPro MX — te pasaron cotización el 12 de marzo. ¿Quieres que les escriba?" },
    ],
  },
  {
    icon: Sparkles,
    title: "Simulación de escenarios",
    desc: "Evalúa decisiones de negocio antes de tomarlas. Dona analiza pros, contras y te da una recomendación.",
    messages: [
      { role: "user" as const, text: "¿Qué pasa si subo precios 15%?" },
      { role: "dona" as const, text: "Con tu margen actual del 22%, subirías a 34%. Riesgo: ~8% de churn. Recomiendo subir 10% primero." },
    ],
  },
  {
    icon: Mail,
    title: "Correo y calendario",
    desc: "Lee, resume y responde correos. Agenda reuniones. Todo sin salir de WhatsApp.",
    messages: [
      { role: "user" as const, text: "¿Qué correos importantes tengo hoy?" },
      { role: "dona" as const, text: "3 urgentes: factura vencida de Adobe, propuesta de cliente nuevo, y confirmación de envío de Shopify." },
    ],
  },
  {
    icon: Calendar,
    title: "Gestión de tareas",
    desc: "Crea, prioriza y da seguimiento a tus pendientes. Dona te recuerda lo importante.",
    messages: [
      { role: "user" as const, text: "Recuérdame llamar al contador el viernes" },
      { role: "dona" as const, text: "Listo. Te recordaré el viernes a las 9am. También tienes pendiente enviar la factura de marzo." },
    ],
  },
  {
    icon: MessageSquare,
    title: "Comandos de voz",
    desc: "Envía notas de voz y Dona las transcribe, interpreta y ejecuta la acción correcta.",
    messages: [
      { role: "user" as const, text: "🎙️ Nota de voz (0:12)" },
      { role: "dona" as const, text: 'Entendido: "Agendar call con Sofía mañana a las 3pm". Ya la agendé en tu calendario.' },
    ],
  },
];

/* ─── FAQ data ─── */
const faqItems = [
  {
    q: "¿Dona puede leer mis correos?",
    a: "Sí. Dona se conecta a Gmail y Outlook para leer, resumir y responder correos. Tú apruebas cada acción.",
  },
  {
    q: "¿Es seguro compartir información de mi negocio?",
    a: "Toda la información se encripta en tránsito y en reposo. No compartimos datos con terceros ni entrenamos modelos con tu información.",
  },
  {
    q: "¿Funciona en español e inglés?",
    a: "Dona entiende y responde en ambos idiomas. Puedes mezclar español e inglés en la misma conversación.",
  },
  {
    q: "¿Necesito instalar una app?",
    a: "No. Dona funciona 100% dentro de WhatsApp. Solo necesitas agregar el número de Dona a tus contactos.",
  },
  {
    q: "¿Cuánto cuesta después del periodo de acceso anticipado?",
    a: "El precio de acceso anticipado de $20/mes se mantiene de por vida para los primeros 100 usuarios. El precio regular será mayor.",
  },
];

/* ─── FAQ accordion ─── */
function FAQ() {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-3 max-w-2xl mx-auto">
      {faqItems.map((item, i) => (
        <div
          key={i}
          className="glass-card rounded-xl overflow-hidden"
        >
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="w-full flex items-center justify-between px-6 py-4 text-left text-white/90 hover:text-white transition-colors cursor-pointer"
          >
            <span className="font-medium text-sm md:text-base pr-4">{item.q}</span>
            <ChevronDown
              className={`w-5 h-5 shrink-0 transition-transform duration-300 ${
                open === i ? "rotate-180" : ""
              }`}
            />
          </button>
          <AnimatePresence>
            {open === i && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className="px-6 pb-4 text-sm text-white/50 leading-relaxed">
                  {item.a}
                </div>
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
  const [activeTab, setActiveTab] = useState(0);
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    // TODO: connect to API route
    setSubmitted(true);
  };

  return (
    <>
      {/* ── Background effects ── */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-[radial-gradient(ellipse_at_center,rgba(79,70,229,0.15)_0%,transparent_70%)]" />
        <div className="absolute bottom-0 right-0 w-[800px] h-[500px] bg-[radial-gradient(ellipse_at_center,rgba(124,58,237,0.1)_0%,transparent_70%)]" />
      </div>

      {/* ── Nav ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[#050a1a]/80 border-b border-white/[0.04]">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 h-16">
          <a href="#" className="text-xl font-bold tracking-tight">
            <span className="text-gradient-main">Dona</span>
          </a>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8 text-sm text-white/50">
            <a href="#capabilities" className="hover:text-white transition-colors">
              Capacidades
            </a>
            <a href="#pricing" className="hover:text-white transition-colors">
              Precios
            </a>
            <a href="#faq" className="hover:text-white transition-colors">
              FAQ
            </a>
            <a
              href="#cta"
              className="btn-primary px-5 py-2 rounded-full text-sm"
            >
              Acceso anticipado
            </a>
          </div>

          {/* Mobile menu toggle */}
          <button
            className="md:hidden text-white/60"
            onClick={() => setMobileMenu(!mobileMenu)}
          >
            {mobileMenu ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {mobileMenu && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="md:hidden border-t border-white/[0.04] overflow-hidden"
            >
              <div className="flex flex-col gap-4 px-6 py-6 text-sm text-white/60">
                <a href="#capabilities" onClick={() => setMobileMenu(false)} className="hover:text-white">
                  Capacidades
                </a>
                <a href="#pricing" onClick={() => setMobileMenu(false)} className="hover:text-white">
                  Precios
                </a>
                <a href="#faq" onClick={() => setMobileMenu(false)} className="hover:text-white">
                  FAQ
                </a>
                <a
                  href="#cta"
                  onClick={() => setMobileMenu(false)}
                  className="btn-primary px-5 py-2.5 rounded-full text-center text-sm"
                >
                  Acceso anticipado
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ── Hero ── */}
      <section className="relative min-h-screen flex items-center justify-center pt-16">
        <div className="max-w-6xl mx-auto px-6 py-24 md:py-32">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            {/* Left */}
            <div>
              <FadeIn>
                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs text-white/50 mb-8">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Acceso anticipado — 100 cupos
                </div>
              </FadeIn>

              <FadeIn delay={0.1}>
                <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.1] tracking-tight mb-6">
                  Dona maneja{" "}
                  <RotatingText />
                  <br />
                  <span className="text-white/40">desde WhatsApp.</span>
                </h1>
              </FadeIn>

              <FadeIn delay={0.2}>
                <p className="text-lg text-white/40 max-w-md mb-8 leading-relaxed">
                  Tu agente de productividad que maneja correo, calendario, tareas, memoria
                  y simulación de escenarios — todo en un solo chat.
                </p>
              </FadeIn>

              <FadeIn delay={0.3}>
                <div className="flex flex-wrap gap-4 mb-12">
                  <a
                    href="#cta"
                    className="btn-primary px-8 py-3.5 rounded-full text-sm flex items-center gap-2 pulse-glow"
                  >
                    Quiero acceso
                    <ArrowRight className="w-4 h-4" />
                  </a>
                  <a
                    href="#capabilities"
                    className="btn-secondary px-8 py-3.5 rounded-full text-sm"
                  >
                    Ver capacidades
                  </a>
                </div>
              </FadeIn>

              <FadeIn delay={0.4}>
                <div className="flex gap-8 text-center">
                  <div>
                    <div className="text-2xl font-bold text-gradient">5</div>
                    <div className="text-xs text-white/30 mt-1">módulos integrados</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gradient">100%</div>
                    <div className="text-xs text-white/30 mt-1">en WhatsApp</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-gradient">24/7</div>
                    <div className="text-xs text-white/30 mt-1">disponible</div>
                  </div>
                </div>
              </FadeIn>
            </div>

            {/* Right — chat mockup */}
            <FadeIn direction="right" delay={0.3} className="hidden md:block">
              <ChatMockup
                messages={[
                  { role: "user", text: "Dona, ¿qué tengo hoy?" },
                  {
                    role: "dona",
                    text: "Buenos días. Tienes 3 correos urgentes, una call a las 11am con Carlos, y tu tarea pendiente de enviar propuesta a NovaTech.",
                  },
                  { role: "user", text: "Resume el correo de Carlos" },
                  {
                    role: "dona",
                    text: "Carlos confirma la reunión de mañana y pregunta si puedes llevar los números del Q1. ¿Le confirmo?",
                  },
                ]}
              />
            </FadeIn>
          </div>
        </div>
      </section>

      {/* ── Pain numbers ── */}
      <section className="section-space">
        <div className="max-w-6xl mx-auto px-6">
          <FadeIn>
            <p className="text-center text-sm uppercase tracking-[0.2em] text-white/30 mb-16">
              El problema que resuelve Dona
            </p>
          </FadeIn>
          <div className="grid md:grid-cols-3 gap-12 text-center">
            {[
              { num: 8, suffix: "+", label: "apps que usas para manejar tu negocio" },
              { num: 3, suffix: "h", label: "perdidas al día cambiando entre herramientas" },
              { num: 47, suffix: "%", label: "de tareas se olvidan sin un sistema central" },
            ].map((item, i) => (
              <FadeIn key={i} delay={i * 0.15}>
                <div className="text-6xl md:text-8xl font-bold text-gradient-main tracking-tighter">
                  <Counter target={item.num} suffix={item.suffix} />
                </div>
                <p className="mt-4 text-sm text-white/40 max-w-[240px] mx-auto">
                  {item.label}
                </p>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <div className="divider-gradient" />

      {/* ── Capabilities ── */}
      <section id="capabilities" className="section-space">
        <div className="max-w-6xl mx-auto px-6">
          <FadeIn>
            <p className="text-sm uppercase tracking-[0.2em] text-white/30 mb-4 text-center">
              Capacidades
            </p>
            <h2 className="text-3xl md:text-5xl font-bold text-center mb-4 tracking-tight">
              Todo lo que Dona <span className="text-gradient">puede hacer</span>
            </h2>
            <p className="text-center text-white/40 max-w-lg mx-auto mb-16">
              Cinco módulos integrados en un solo chat de WhatsApp. Sin apps extra, sin fricción.
            </p>
          </FadeIn>

          <div className="grid md:grid-cols-12 gap-8">
            {/* Tabs */}
            <div className="md:col-span-4 flex md:flex-col gap-2">
              {capabilities.map((cap, i) => {
                const Icon = cap.icon;
                return (
                  <button
                    key={i}
                    onClick={() => setActiveTab(i)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all cursor-pointer w-full ${
                      activeTab === i
                        ? "bg-white/[0.06] border border-white/[0.1] text-white"
                        : "text-white/40 hover:text-white/60 hover:bg-white/[0.02]"
                    }`}
                  >
                    <Icon className="w-5 h-5 shrink-0" />
                    <span className="text-sm font-medium hidden md:inline">{cap.title}</span>
                  </button>
                );
              })}
            </div>

            {/* Content */}
            <div className="md:col-span-8">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.4 }}
                  className="grid md:grid-cols-2 gap-8 items-start"
                >
                  <div>
                    <h3 className="text-xl font-semibold mb-3">
                      {capabilities[activeTab].title}
                    </h3>
                    <p className="text-white/40 text-sm leading-relaxed">
                      {capabilities[activeTab].desc}
                    </p>
                  </div>
                  <ChatMockup messages={capabilities[activeTab].messages} />
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </section>

      <div className="divider-gradient" />

      {/* ── Why Different ── */}
      <section className="section-space">
        <div className="max-w-6xl mx-auto px-6">
          <FadeIn>
            <p className="text-sm uppercase tracking-[0.2em] text-white/30 mb-4 text-center">
              Por qué Dona
            </p>
            <h2 className="text-3xl md:text-5xl font-bold text-center mb-16 tracking-tight">
              Diseñada para <span className="text-gradient">emprendedores</span>
            </h2>
          </FadeIn>

          <div className="grid md:grid-cols-2 gap-6">
            {[
              {
                icon: Brain,
                title: "Memoria que aprende",
                desc: "No repites información. Dona recuerda cada dato, contacto y decisión. Pregúntale lo que sea.",
              },
              {
                icon: Sparkles,
                title: "Escenarios simulados",
                desc: "¿Subir precios? ¿Contratar? Dona analiza el impacto antes de que tomes la decisión.",
              },
              {
                icon: Shield,
                title: "Privacidad primero",
                desc: "Tu información está encriptada y nunca se comparte. No entrenamos modelos con tus datos.",
              },
              {
                icon: Globe,
                title: "Hecho para hispanos en USA",
                desc: "Entiende español, inglés y Spanglish. Diseñada para la realidad del emprendedor latino.",
              },
            ].map((card, i) => {
              const Icon = card.icon;
              return (
                <FadeIn key={i} delay={i * 0.1}>
                  <div className="glass-card rounded-2xl p-8 h-full">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#4F46E5]/20 to-[#7C3AED]/20 flex items-center justify-center mb-5">
                      <Icon className="w-6 h-6 text-[#818CF8]" />
                    </div>
                    <h3 className="text-lg font-semibold mb-2">{card.title}</h3>
                    <p className="text-sm text-white/40 leading-relaxed">{card.desc}</p>
                  </div>
                </FadeIn>
              );
            })}
          </div>
        </div>
      </section>

      <div className="divider-gradient" />

      {/* ── Testimonials ── */}
      <section className="section-space">
        <div className="max-w-6xl mx-auto px-6">
          <FadeIn>
            <p className="text-sm uppercase tracking-[0.2em] text-white/30 mb-4 text-center">
              Usuarios beta
            </p>
            <h2 className="text-3xl md:text-5xl font-bold text-center mb-16 tracking-tight">
              Lo que dicen los <span className="text-gradient">primeros usuarios</span>
            </h2>
          </FadeIn>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                name: "Carlos M.",
                role: "Fundador, importadora en Miami",
                text: "Dona me ahorra 2 horas al día. Ya no tengo que revisar correos uno por uno — me manda un resumen y responde por mí.",
              },
              {
                name: "Valeria R.",
                role: "Consultora de marketing digital",
                text: "La simulación de escenarios es increíble. Le pregunté si debía subir tarifas y me dio un análisis que mi contador no me había dado.",
              },
              {
                name: "Diego F.",
                role: "E-commerce, envíos a LATAM",
                text: "Lo mejor es la memoria. Le digo algo una vez y nunca lo olvida. Es como tener un asistente que realmente escucha.",
              },
            ].map((t, i) => (
              <FadeIn key={i} delay={i * 0.1}>
                <div className="glass-card rounded-2xl p-8 h-full flex flex-col">
                  <p className="text-sm text-white/50 leading-relaxed flex-1 mb-6">
                    &ldquo;{t.text}&rdquo;
                  </p>
                  <div>
                    <p className="text-sm font-medium text-white/80">{t.name}</p>
                    <p className="text-xs text-white/30">{t.role}</p>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      <div className="divider-gradient" />

      {/* ── Pricing ── */}
      <section id="pricing" className="section-space">
        <div className="max-w-6xl mx-auto px-6">
          <FadeIn>
            <p className="text-sm uppercase tracking-[0.2em] text-white/30 mb-4 text-center">
              Precios
            </p>
            <h2 className="text-3xl md:text-5xl font-bold text-center mb-4 tracking-tight">
              Simple y <span className="text-gradient">transparente</span>
            </h2>
            <p className="text-center text-white/40 max-w-md mx-auto mb-16">
              Precio especial de por vida para los primeros 100 usuarios.
            </p>
          </FadeIn>

          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {/* Early Access */}
            <FadeIn delay={0}>
              <div className="glass-card rounded-2xl p-8 relative overflow-hidden">
                <p className="text-sm text-white/40 mb-1">Acceso Anticipado</p>
                <div className="flex items-end gap-1 mb-6">
                  <span className="text-4xl font-bold">$20</span>
                  <span className="text-white/30 mb-1">/mes</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {[
                    "Correo y calendario",
                    "Gestión de tareas",
                    "Memoria inteligente",
                    "Simulación de escenarios",
                    "Notas de voz",
                    "Soporte prioritario",
                  ].map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-white/50">
                      <CheckCircle2 className="w-4 h-4 text-[#818CF8] shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <a
                  href="#cta"
                  className="btn-primary w-full py-3 rounded-full text-sm text-center block"
                >
                  Reservar cupo
                </a>
              </div>
            </FadeIn>

            {/* Pro */}
            <FadeIn delay={0.1}>
              <div className="glass-card rounded-2xl p-8 border-[#4F46E5]/30 relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-[#4F46E5] to-[#7C3AED]" />
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm text-white/40">Pro</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#4F46E5]/20 text-[#818CF8]">
                    Próximamente
                  </span>
                </div>
                <div className="flex items-end gap-1 mb-6">
                  <span className="text-4xl font-bold">$40</span>
                  <span className="text-white/30 mb-1">/mes</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {[
                    "Todo del plan anterior",
                    "Integraciones avanzadas",
                    "Multi-negocio",
                    "API personalizada",
                    "Automatizaciones",
                    "Análisis y reportes",
                  ].map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-white/50">
                      <CheckCircle2 className="w-4 h-4 text-[#818CF8] shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button className="btn-secondary w-full py-3 rounded-full text-sm cursor-not-allowed opacity-50">
                  Próximamente
                </button>
              </div>
            </FadeIn>

            {/* Enterprise */}
            <FadeIn delay={0.2}>
              <div className="glass-card rounded-2xl p-8">
                <div className="flex items-center gap-2 mb-1">
                  <p className="text-sm text-white/40">Enterprise</p>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#4F46E5]/20 text-[#818CF8]">
                    Próximamente
                  </span>
                </div>
                <div className="flex items-end gap-1 mb-6">
                  <span className="text-4xl font-bold">Custom</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {[
                    "Todo del plan Pro",
                    "Equipo ilimitado",
                    "SLA garantizado",
                    "Onboarding dedicado",
                    "Integraciones custom",
                    "Soporte 24/7",
                  ].map((f, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-white/50">
                      <CheckCircle2 className="w-4 h-4 text-[#818CF8] shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button className="btn-secondary w-full py-3 rounded-full text-sm cursor-not-allowed opacity-50">
                  Próximamente
                </button>
              </div>
            </FadeIn>
          </div>
        </div>
      </section>

      <div className="divider-gradient" />

      {/* ── CTA + Form ── */}
      <section id="cta" className="section-space">
        <div className="max-w-2xl mx-auto px-6 text-center">
          <FadeIn>
            <h2 className="text-3xl md:text-5xl font-bold mb-4 tracking-tight">
              Reserva tu <span className="text-gradient-main">cupo</span>
            </h2>
            <p className="text-white/40 mb-10 max-w-md mx-auto">
              Solo 100 cupos en acceso anticipado. Ingresa tu correo para asegurar tu lugar.
            </p>
          </FadeIn>

          <FadeIn delay={0.15}>
            {!submitted ? (
              <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@correo.com"
                  required
                  className="flex-1 px-5 py-3.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-[#4F46E5]/50 transition-colors"
                />
                <button
                  type="submit"
                  className="btn-primary px-8 py-3.5 rounded-full text-sm flex items-center justify-center gap-2 whitespace-nowrap"
                >
                  Reservar
                  <Send className="w-4 h-4" />
                </button>
              </form>
            ) : (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-card rounded-2xl p-8 max-w-md mx-auto"
              >
                <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
                <h3 className="text-xl font-semibold mb-2">Cupo reservado</h3>
                <p className="text-sm text-white/40">
                  Te enviaremos un correo con los próximos pasos. Bienvenido a Dona.
                </p>
              </motion.div>
            )}
          </FadeIn>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section id="faq" className="section-space">
        <div className="max-w-6xl mx-auto px-6">
          <FadeIn>
            <p className="text-sm uppercase tracking-[0.2em] text-white/30 mb-4 text-center">
              FAQ
            </p>
            <h2 className="text-3xl md:text-5xl font-bold text-center mb-16 tracking-tight">
              Preguntas <span className="text-gradient">frecuentes</span>
            </h2>
          </FadeIn>
          <FadeIn delay={0.1}>
            <FAQ />
          </FadeIn>
        </div>
      </section>

      <div className="divider-gradient" />

      {/* ── Footer ── */}
      <footer className="py-12">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <span className="text-lg font-bold text-gradient-main">Dona</span>
              <span className="text-xs text-white/20">
                Tu agente de productividad en WhatsApp
              </span>
            </div>
            <div className="flex items-center gap-6 text-sm text-white/30">
              <a href="mailto:hola@usadona.com" className="hover:text-white/60 transition-colors">
                hola@usadona.com
              </a>
              <a
                href="https://instagram.com/usadona"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-white/60 transition-colors"
              >
                Instagram
              </a>
              <a
                href="https://twitter.com/usadona"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-white/60 transition-colors"
              >
                X / Twitter
              </a>
            </div>
          </div>
          <div className="mt-8 text-center text-xs text-white/15">
            &copy; {new Date().getFullYear()} Dona. Todos los derechos reservados.
          </div>
        </div>
      </footer>
    </>
  );
}
