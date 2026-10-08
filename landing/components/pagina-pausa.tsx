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
    <main className="relative z-[2] flex min-h-screen items-center justify-center bg-[color:var(--bg)] px-6 py-16 text-[color:var(--ink)]">
      <div className="surface-static w-full max-w-lg p-10 sm:p-12">
        <p className="text-2xl font-semibold tracking-tight">Dona</p>
        <p className="eyebrow mt-8">Servicio en pausa</p>
        <h1 className="mt-4 text-3xl font-medium leading-tight tracking-tight sm:text-4xl">
          Dona está en pausa
        </h1>
        <p className="mt-5 text-base leading-relaxed text-[color:var(--ink)]">
          {MENSAJE_PAUSA}
        </p>
        {detalle && (
          <p className="mt-3 text-sm leading-relaxed text-[color:var(--muted)]">
            {detalle}
          </p>
        )}
        <nav
          aria-label="Documentos legales"
          className="mt-10 flex flex-wrap gap-x-6 gap-y-2 border-t border-[color:var(--line)] pt-6 text-sm text-[color:var(--muted)]"
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
