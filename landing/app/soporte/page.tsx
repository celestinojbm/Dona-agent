import Link from "next/link";
import { Mail, ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Soporte — Dona",
  description:
    "Cómo contactar al equipo de Dona para temas de cuenta, suscripción, pagos o uso del servicio.",
};

export default function SoportePage() {
  return (
    <div className="min-h-screen px-6 py-24 md:py-32 relative z-[2]">
      <div className="max-w-2xl mx-auto">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-white/40 hover:text-white/70 transition-colors mb-12 font-light"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver al inicio
        </Link>

        <h1 className="text-4xl md:text-5xl font-normal text-white mb-6 tracking-tighter">
          Soporte Dona
        </h1>

        <p className="text-white/45 font-light leading-relaxed mb-10">
          Si necesitas ayuda con tu cuenta, suscripción, pagos o uso de Dona,
          puedes escribirnos. Respondemos lo antes posible.
        </p>

        <div className="glass-card rounded-2xl p-8 mb-10">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center shrink-0">
              <Mail className="w-6 h-6 text-white/40" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-widest text-white/35 mb-2 font-light">
                Email de soporte
              </p>
              <a
                href="mailto:hola@usadona.com"
                className="text-xl text-white nav-link"
              >
                hola@usadona.com
              </a>
              <p className="text-sm text-white/40 font-light mt-3 leading-relaxed">
                Para temas de facturación, cancelación o cualquier duda sobre
                el servicio, escríbenos a esta dirección y un humano te
                responderá lo antes posible.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-6 text-white/45 font-light leading-relaxed text-sm">
          <div>
            <h2 className="text-base text-white/70 font-normal mb-2">
              ¿Qué incluir en tu mensaje?
            </h2>
            <p>
              Para ayudarte más rápido, incluye el correo o teléfono asociado a
              tu cuenta y describe qué intentaste hacer y qué pasó. Si es un
              problema de pago, agregar la fecha aproximada de la transacción
              ayuda mucho.
            </p>
          </div>
          <div>
            <h2 className="text-base text-white/70 font-normal mb-2">
              Tiempos de respuesta
            </h2>
            <p>
              Atendemos los mensajes de lunes a viernes en horario hábil de
              Estados Unidos. Para temas urgentes de facturación o cancelación
              respondemos prioritariamente.
            </p>
          </div>
          <div>
            <h2 className="text-base text-white/70 font-normal mb-2">
              Cancelación de suscripción
            </h2>
            <p>
              Puedes cancelar tu suscripción cuando quieras desde tu{" "}
              <Link href="/dashboard" className="nav-link text-white/70">
                dashboard
              </Link>{" "}
              o escribiéndonos al email de soporte. La cancelación aplica al
              siguiente periodo; los créditos ya acreditados quedan disponibles
              para usar.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
