// landing/components/pagina-pausa.tsx — Página completa "Dona en pausa".
//
// La renderizan todas las páginas públicas que antes vendían, cobraban o
// daban acceso (inicio, checkout, success, cancel, login, dashboard,
// soporte). Componente de servidor: no carga JS de cliente ni consulta
// Stripe, la sesión o el backend.
//
// Sin contacto todavía: el correo se añade cuando Celestino confirme que la
// dirección recibe mensajes (ver docs/transition/dona-app-first/).

import Link from "next/link";
import { MENSAJE_PAUSA } from "@/lib/pausa";

interface PaginaPausaProps {
  /** Línea específica de la ruta (p. ej. "Esta página no confirma pagos."). */
  detalle?: string;
}

export default function PaginaPausa({ detalle }: PaginaPausaProps) {
  return (
    <main className="tipo-landing relative z-[2] flex min-h-screen items-center justify-center bg-[color:var(--bg)] px-5 py-16 text-[color:var(--ink)] sm:px-8 sm:py-20">
      <div className="surface-static w-full max-w-3xl p-8 sm:p-12 md:p-14">
        <p className="tipo-marca font-semibold">Dona</p>
        <p className="eyebrow mt-8">Servicio en pausa</p>
        <h1 className="tipo-hero mt-5 font-medium">
          Dona está en pausa
        </h1>
        <p className="tipo-cuerpo mt-6 text-[color:var(--ink)]">
          {MENSAJE_PAUSA}
        </p>
        {detalle && (
          <p className="tipo-cuerpo mt-4 text-[color:var(--muted)]">
            {detalle}
          </p>
        )}
        <nav
          aria-label="Documentos legales"
          className="tipo-nav mt-12 flex flex-wrap gap-x-8 gap-y-3 border-t border-[color:var(--line)] pt-8 text-[color:var(--muted)]"
        >
          <Link href="/terminos-y-condiciones" className="hover:text-[color:var(--ink)]">
            Términos y condiciones
          </Link>
          <Link href="/politica-de-privacidad" className="hover:text-[color:var(--ink)]">
            Política de privacidad
          </Link>
        </nav>
      </div>
    </main>
  );
}
