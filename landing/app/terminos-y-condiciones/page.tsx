import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Términos y condiciones — Dona",
  description:
    "Condiciones de uso del servicio Dona, suscripciones, pagos y responsabilidades.",
};

const ULTIMA_ACTUALIZACION = "2 de mayo de 2026";

export default function TerminosYCondicionesPage() {
  return (
    <div className="min-h-screen px-6 py-24 md:py-32 relative z-[2]">
      <div className="max-w-3xl mx-auto">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-white/40 hover:text-white/70 transition-colors mb-12 font-light"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver al inicio
        </Link>

        <h1 className="text-4xl md:text-5xl font-normal text-white mb-3 tracking-tighter">
          Términos y condiciones
        </h1>
        <p className="text-xs uppercase tracking-widest text-white/35 mb-10 font-light">
          Última actualización: {ULTIMA_ACTUALIZACION}
        </p>

        <div className="space-y-8 text-white/55 font-light leading-relaxed text-[15px]">
          <p>
            Estos términos describen las condiciones de uso del servicio
            Dona. Al crear una cuenta, suscribirte a un plan o usar el
            servicio aceptas estos términos.
          </p>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Qué es Dona
            </h2>
            <p>
              Dona es un asistente inteligente para negocios, accesible
              principalmente por WhatsApp. Ayuda a sus usuarios con tareas
              como gestión de mensajes, calendario, recordatorios, análisis
              de información y otras funcionalidades que pueden cambiar con
              el tiempo.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Uso permitido
            </h2>
            <p className="mb-3">Al usar Dona te comprometes a no:</p>
            <ul className="space-y-2 ml-4">
              <li>· Usar el servicio para actividades ilegales o fraudulentas.</li>
              <li>
                · Enviar spam, contenido abusivo o material que viole derechos
                de terceros.
              </li>
              <li>
                · Intentar acceder a cuentas de otros usuarios, vulnerar la
                seguridad del servicio o interferir con su normal
                funcionamiento.
              </li>
              <li>
                · Usar Dona para tomar decisiones automatizadas en ámbitos
                donde la regulación exige supervisión humana sin que tú
                ejerzas esa supervisión.
              </li>
            </ul>
            <p className="mt-3">
              Nos reservamos el derecho de suspender o cancelar cuentas que
              incumplan estos términos.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Suscripciones y pagos
            </h2>
            <ul className="space-y-2 ml-4">
              <li>
                · Los pagos son procesados por{" "}
                <span className="text-white/80">Stripe</span>. Al suscribirte
                aceptas también las condiciones de uso de ese proveedor para
                el procesamiento de tu pago.
              </li>
              <li>
                · Los planes y precios pueden cambiar; te avisaremos antes de
                aplicar un cambio que afecte tu suscripción activa.
              </li>
              <li>
                · Las cancelaciones aplican hacia adelante: tu plan continúa
                hasta el final del periodo ya pagado y no se renueva. No se
                generan reembolsos por periodos parciales salvo que la ley
                aplicable lo exija.
              </li>
              <li>
                · Si una renovación falla podemos suspender el acceso a
                funciones pagas hasta que el problema de pago se resuelva.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Créditos
            </h2>
            <p>
              Algunas funciones de Dona consumen créditos asociados a tu
              cuenta. Los créditos pueden tener límites técnicos o de
              disponibilidad y pueden no estar disponibles en todo momento.
              Los créditos no son canjeables por dinero ni transferibles
              entre cuentas.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Disponibilidad del servicio
            </h2>
            <p>
              Dona puede cambiar, mejorar, agregar o retirar funcionalidades
              en cualquier momento. También puede haber interrupciones
              programadas o no programadas para mantenimiento, fallas de
              terceros o causas fuera de nuestro control. No garantizamos
              disponibilidad ininterrumpida.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Responsabilidad del usuario
            </h2>
            <p>
              Dona ayuda con tareas, sugerencias y automatizaciones, pero
              <span className="text-white/80">
                {" "}
                el usuario es responsable de revisar las decisiones
                importantes
              </span>{" "}
              antes de ejecutarlas, especialmente las que tengan impacto
              financiero, legal o sobre terceros. Las respuestas generadas
              por modelos de inteligencia artificial pueden contener errores;
              úsalas como apoyo, no como única fuente de verdad.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Propiedad
            </h2>
            <p>
              Tú conservas la propiedad del contenido que envías a Dona. Nos
              das una licencia limitada para procesar ese contenido con el
              único fin de prestar el servicio. La marca Dona, su software y
              su diseño son propiedad de Dona y no se transfieren con el uso
              del servicio.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Limitación de responsabilidad
            </h2>
            <p>
              En la medida permitida por la ley aplicable, Dona se ofrece
              &ldquo;tal cual&rdquo;, sin garantías expresas o implícitas.
              No somos responsables por daños indirectos o consecuentes
              derivados del uso del servicio. Nuestra responsabilidad total
              ante cualquier reclamo no superará el monto pagado por ti en
              los doce meses anteriores al hecho que dio origen al reclamo.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Cambios a estos términos
            </h2>
            <p>
              Podemos actualizar estos términos para reflejar cambios en el
              servicio o en requerimientos legales. Cuando lo hagamos
              actualizaremos la fecha de última actualización al inicio del
              documento. El uso continuado del servicio después de un cambio
              implica aceptación del cambio.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Contacto
            </h2>
            <p>
              Para cualquier duda sobre estos términos puedes escribirnos a{" "}
              <a
                href="mailto:hola@usadona.com"
                className="nav-link text-white/80"
              >
                hola@usadona.com
              </a>{" "}
              o visitar nuestra{" "}
              <Link href="/soporte" className="nav-link text-white/80">
                página de soporte
              </Link>
              .
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
