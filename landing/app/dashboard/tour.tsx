"use client";

// landing/app/dashboard/tour.tsx — T2.0.D
// First-login tour del dashboard. Modal con steps que explica al
// usuario premium qué puede hacer en cada sección. Persistencia con
// localStorage (no toca DB). Cierra con ESC o "Saltar"; al terminar
// guarda flag y no vuelve a aparecer.
//
// Decisiones:
//   - Sin DB writes para mantener PR chico y reversible. localStorage
//     basta para una experiencia de primer login. Si el usuario cambia
//     de dispositivo / limpia caché, vuelve a verlo (aceptable).
//   - El CTA "Empezar diagnóstico" abre wa.me con mensaje pre-llenado
//     pero el usuario debe enviarlo manualmente. NO hay envío
//     automático server-side.
//   - Solo se renderiza si la suscripción está activa (estado='active'
//     o 'past_due'); usuarios cancelados no necesitan tour, ven el
//     CTA "Reactivar plan" del dashboard.

import { useEffect, useState, useCallback } from "react";
import {
  Wallet,
  CreditCard,
  Zap,
  Receipt,
  Shield,
  Mail,
  MessageSquare,
  ArrowRight,
  ArrowLeft,
  X,
  CheckCircle2,
} from "lucide-react";

const TOUR_STORAGE_KEY = "dona_tour_visto";
const TOUR_STORAGE_VALUE = "1";

type StepIcon = typeof Wallet;

interface Step {
  icon: StepIcon;
  titulo: string;
  descripcion: string;
}

const STEPS: readonly Step[] = [
  {
    icon: Wallet,
    titulo: "Bienvenido a tu dashboard",
    descripcion:
      "Aquí encuentras todo lo que pasa con tu cuenta de Dona en un solo lugar. Veamos las secciones principales en 30 segundos.",
  },
  {
    icon: Wallet,
    titulo: "Saldo y créditos",
    descripcion:
      "Tu saldo actual está arriba. Cada renovación de tu plan suma los créditos mensuales correspondientes. Los créditos no expiran y se acumulan.",
  },
  {
    icon: CreditCard,
    titulo: "Plan activo",
    descripcion:
      "Aquí ves tu plan vigente y la próxima fecha de renovación. Si necesitas cancelar o cambiar el plan, abre el portal de facturación más abajo.",
  },
  {
    icon: Zap,
    titulo: "Comprar créditos extra",
    descripcion:
      "¿Necesitas más créditos sin cambiar de plan? Compra paquetes one-time desde la sección 'Comprar créditos extra'. Los créditos se suman a tu saldo y no expiran.",
  },
  {
    icon: Receipt,
    titulo: "Movimientos recientes",
    descripcion:
      "Cada cargo y cada consumo queda registrado en tu historial. Puedes verificar cuándo se acreditaron créditos y en qué se gastaron.",
  },
  {
    icon: Shield,
    titulo: "Gestionar facturación",
    descripcion:
      "Desde el botón 'Gestionar facturación' abres el portal de Stripe para cambiar tu método de pago, descargar facturas, pausar o cancelar tu plan.",
  },
  {
    icon: Mail,
    titulo: "¿Necesitas ayuda?",
    descripcion:
      "Para cualquier duda sobre tu cuenta, suscripción o uso de Dona, escríbenos a hola@usadona.com o visita la página de soporte.",
  },
  {
    icon: MessageSquare,
    titulo: "Próximo paso · diagnóstico por WhatsApp",
    descripcion:
      "Para que Dona te ayude de verdad, cuéntale sobre tu negocio. Abre WhatsApp y escribe 'hola' para empezar el diagnóstico inicial. Solo te tomará unos minutos a lo largo de los próximos días.",
  },
];

const DEFAULT_DIAGNOSTICO_TEXT =
  "hola Dona, quiero empezar el diagnóstico de mi negocio.";

function dashboardWhatsAppUrl(): string {
  // NEXT_PUBLIC_DONA_WHATSAPP_NUMBER es opcional. Si está presente, abre
  // un chat directo con Dona con un texto pre-llenado. Si no, usa
  // wa.me sin número, que abre WhatsApp y deja al usuario elegir el
  // contacto de Dona ya guardado. Sin envío automático.
  const num =
    process.env.NEXT_PUBLIC_DONA_WHATSAPP_NUMBER?.trim().replace(/^\+/, "") ||
    "";
  const text = encodeURIComponent(DEFAULT_DIAGNOSTICO_TEXT);
  if (num && /^\d{10,15}$/.test(num)) {
    return `https://wa.me/${num}?text=${text}`;
  }
  return `https://wa.me/?text=${text}`;
}

interface TourDashboardProps {
  /** Si false, el tour no se monta. Útil si la sub está canceled. */
  habilitado: boolean;
}

export default function TourDashboard({ habilitado }: TourDashboardProps) {
  const [montado, setMontado] = useState(false);
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  // Effect 1: detectar si ya se vio el tour (al mount).
  // La regla react-hooks/set-state-in-effect (Next 16) desaconseja
  // setState en effects, recomendando Suspense + use(promise). Aquí el
  // patrón es legítimo: leemos localStorage (sólo disponible en cliente,
  // no en SSR) y decidimos visibilidad. No hay alternativa server-side
  // sin agregar storage backend, y eso violaría el scope T2.0.D
  // ("Persistencia local segura aceptable si evita tocar DB").
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMontado(true);
    if (!habilitado) return;
    try {
      const yaVisto = window.localStorage.getItem(TOUR_STORAGE_KEY);
      if (yaVisto !== TOUR_STORAGE_VALUE) {
        setVisible(true);
      }
    } catch {
      // localStorage puede fallar (modo privado en Safari); no mostrar
      // tour antes que romper la UI.
    }
  }, [habilitado]);

  const cerrar = useCallback(() => {
    try {
      window.localStorage.setItem(TOUR_STORAGE_KEY, TOUR_STORAGE_VALUE);
    } catch {
      // Si localStorage falla, igual cerramos visualmente.
    }
    setVisible(false);
  }, []);

  // Effect 2: cerrar con ESC.
  useEffect(() => {
    if (!visible) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        cerrar();
      } else if (e.key === "ArrowRight") {
        setStep((s) => Math.min(s + 1, STEPS.length - 1));
      } else if (e.key === "ArrowLeft") {
        setStep((s) => Math.max(s - 1, 0));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, cerrar]);

  if (!montado || !habilitado || !visible) {
    return null;
  }

  const current = STEPS[step];
  const Icon = current.icon;
  const esUltimo = step === STEPS.length - 1;
  const esPrimero = step === 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-titulo"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
    >
      {/* Backdrop con blur */}
      <button
        type="button"
        aria-label="Cerrar tour"
        onClick={cerrar}
        className="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-default"
      />

      {/* Modal card */}
      <div className="glass-card relative z-10 rounded-2xl max-w-md w-full p-8 text-white">
        {/* Cerrar X arriba derecha */}
        <button
          type="button"
          aria-label="Saltar tour"
          onClick={cerrar}
          className="absolute top-4 right-4 text-white/40 hover:text-white/80 transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Icono + paso */}
        <div className="flex items-center gap-4 mb-6">
          <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center shrink-0">
            <Icon className="w-6 h-6 text-white/70" />
          </div>
          <div className="text-xs uppercase tracking-widest text-white/35 font-light">
            Paso {step + 1} de {STEPS.length}
          </div>
        </div>

        {/* Título y descripción */}
        <h2
          id="tour-titulo"
          className="text-xl font-normal text-white tracking-tight mb-3"
        >
          {current.titulo}
        </h2>
        <p className="text-sm text-white/55 font-light leading-relaxed mb-8">
          {current.descripcion}
        </p>

        {/* Progress dots */}
        <div className="flex items-center gap-1.5 mb-6" aria-hidden="true">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 rounded-full transition-all ${
                i === step
                  ? "w-6 bg-white/60"
                  : i < step
                    ? "w-1.5 bg-white/30"
                    : "w-1.5 bg-white/10"
              }`}
            />
          ))}
        </div>

        {/* Botones de navegación */}
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(s - 1, 0))}
            disabled={esPrimero}
            className="btn-secondary px-4 py-2.5 rounded-full text-sm flex items-center gap-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ArrowLeft className="w-4 h-4" />
            Anterior
          </button>

          {esUltimo ? (
            <div className="flex items-center gap-2">
              <a
                href={dashboardWhatsAppUrl()}
                target="_blank"
                rel="noopener noreferrer"
                onClick={cerrar}
                className="btn-primary px-5 py-2.5 rounded-full text-sm flex items-center gap-2"
              >
                <MessageSquare className="w-4 h-4" />
                Empezar diagnóstico
              </a>
              <button
                type="button"
                onClick={cerrar}
                className="btn-secondary px-4 py-2.5 rounded-full text-sm flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-4 h-4" />
                Listo
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setStep((s) => Math.min(s + 1, STEPS.length - 1))}
              className="btn-primary px-5 py-2.5 rounded-full text-sm flex items-center gap-1.5"
            >
              Siguiente
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Saltar (texto pequeño) */}
        {!esUltimo && (
          <button
            type="button"
            onClick={cerrar}
            className="block mx-auto mt-4 text-xs text-white/30 hover:text-white/60 transition-colors font-light"
          >
            Saltar tour
          </button>
        )}
      </div>
    </div>
  );
}

// Export del helper para tests / reuso futuro.
export { dashboardWhatsAppUrl, STEPS, TOUR_STORAGE_KEY };
