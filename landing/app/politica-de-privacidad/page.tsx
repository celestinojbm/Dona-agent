import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Política de privacidad — Dona",
  description:
    "Cómo Dona recolecta, usa y protege la información de sus usuarios.",
};

const ULTIMA_ACTUALIZACION = "2 de mayo de 2026";

export default function PoliticaDePrivacidadPage() {
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
          Política de privacidad
        </h1>
        <p className="text-xs uppercase tracking-widest text-white/35 mb-10 font-light">
          Última actualización: {ULTIMA_ACTUALIZACION}
        </p>

        <div className="space-y-8 text-white/55 font-light leading-relaxed text-[15px]">
          <p>
            En Dona valoramos la privacidad de quienes usan nuestro servicio.
            Este documento describe, en lenguaje simple, qué información
            recolectamos, para qué la usamos y con quién la compartimos. Al
            usar Dona aceptas las prácticas descritas aquí.
          </p>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Qué datos recolectamos
            </h2>
            <p className="mb-3">
              Para prestar el servicio recolectamos la información mínima
              necesaria, que puede incluir:
            </p>
            <ul className="space-y-2 ml-4">
              <li>· Nombre, correo electrónico y número de teléfono.</li>
              <li>
                · Datos de cuenta como tu plan, créditos disponibles y
                preferencias de configuración.
              </li>
              <li>
                · Mensajes y archivos que envías a Dona por WhatsApp u otros
                canales.
              </li>
              <li>
                · Información necesaria para operar integraciones que tú
                autorizas (por ejemplo, tokens de acceso a servicios externos
                como correo o calendario).
              </li>
              <li>
                · Datos técnicos básicos como direcciones IP, tipo de
                dispositivo y registros de actividad para seguridad y
                diagnóstico.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Para qué usamos tus datos
            </h2>
            <ul className="space-y-2 ml-4">
              <li>· Prestar y mantener el servicio.</li>
              <li>· Procesar pagos y administrar tu suscripción.</li>
              <li>· Responder tus solicitudes de soporte.</li>
              <li>
                · Detectar fraudes, abusos y proteger la integridad del
                servicio.
              </li>
              <li>
                · Mejorar la calidad del producto y diagnosticar problemas
                técnicos.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Proveedores con los que trabajamos
            </h2>
            <p className="mb-3">
              Para operar Dona usamos un conjunto acotado de proveedores
              técnicos, que procesan información solo para los fines
              estrictamente necesarios:
            </p>
            <ul className="space-y-2 ml-4">
              <li>
                · <span className="text-white/80">Stripe</span> para procesar
                pagos y administrar suscripciones.
              </li>
              <li>
                · Proveedores de mensajería para entregar y recibir mensajes
                de WhatsApp.
              </li>
              <li>
                · Infraestructura cloud para alojar la aplicación, la base de
                datos y los servicios asociados.
              </li>
              <li>
                · Proveedores de modelos de inteligencia artificial que
                generan respuestas a partir del contenido que tú envías.
              </li>
            </ul>
            <p className="mt-3">
              Estos proveedores acceden a la información estrictamente
              necesaria para cumplir su función y están obligados a tratarla
              con medidas de seguridad razonables.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Lo que no hacemos
            </h2>
            <ul className="space-y-2 ml-4">
              <li>
                · <span className="text-white/80">No vendemos</span> tu
                información personal a terceros.
              </li>
              <li>
                · No usamos tus datos para entrenar modelos propios públicos.
              </li>
              <li>
                · No compartimos información con anunciantes ni redes
                publicitarias.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Seguridad
            </h2>
            <p>
              Aplicamos medidas razonables de seguridad para proteger la
              información, incluyendo cifrado en tránsito (TLS) en todas las
              comunicaciones y cifrado en reposo de credenciales sensibles
              (por ejemplo, tokens de integraciones). Ningún sistema es
              perfectamente seguro; ante un incidente que afecte tu
              información, te lo comunicaremos en los plazos que correspondan.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Tus derechos
            </h2>
            <p>
              Puedes solicitar acceso a la información personal que tenemos
              sobre ti, pedir su corrección o pedir su eliminación. Para
              ejercer cualquiera de estos derechos escríbenos al correo
              indicado más abajo y te responderemos en un plazo razonable.
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Contacto
            </h2>
            <p>
              Para cualquier duda relacionada con esta política de privacidad
              puedes escribirnos a{" "}
              <a
                href="mailto:hola@usadona.com"
                className="nav-link text-white/80"
              >
                hola@usadona.com
              </a>
              . También encontrarás más información de contacto en nuestra{" "}
              <Link href="/soporte" className="nav-link text-white/80">
                página de soporte
              </Link>
              .
            </p>
          </section>

          <section>
            <h2 className="text-xl text-white font-normal mb-3 tracking-tight">
              Cambios a esta política
            </h2>
            <p>
              Podemos actualizar esta política para reflejar cambios en el
              servicio o en requerimientos legales. Cuando lo hagamos
              actualizaremos la fecha de última actualización al inicio del
              documento.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
