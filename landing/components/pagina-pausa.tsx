// landing/components/pagina-pausa.tsx — Pantalla pública mientras Dona está en pausa.
//
// Antes era un callejón sin salida ("Dona está en pausa" repetido tres veces,
// sin ninguna acción). Ahora es una lista de espera con invitaciones (#334):
// dejar el correo o canjear un código. No vende, no cobra, no pide contraseña
// ni da acceso: la pausa sigue (lib/pausa.ts). Los correos se guardan en el
// backend; el aviso por correo está apagado.
//
// La renderizan las páginas que antes vendían o daban acceso (inicio,
// checkout, success, cancel, login, dashboard, soporte). Componente de
// servidor; solo el formulario es cliente.

import Link from "next/link";
import ListaEsperaForm from "@/components/lista-espera-form";

interface PaginaPausaProps {
  /** Línea específica de la ruta (p. ej. "Esta página no confirma pagos."). */
  detalle?: string;
}

export default function PaginaPausa({ detalle }: PaginaPausaProps) {
  return (
    <main className="relative z-[2] flex min-h-dvh flex-col bg-[color:var(--bg)] px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(3rem,env(safe-area-inset-top))] text-[color:var(--ink)] sm:items-center sm:justify-center">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="grid h-11 w-11 place-items-center rounded-2xl bg-[color:var(--ink)] text-xl font-semibold text-[color:var(--bg)]"
          >
            D
          </span>
          <p className="text-xl font-semibold tracking-tight">Dona</p>
        </div>

        <h1 className="mt-10 text-[28px] font-semibold leading-tight tracking-tight">
          Dona abre por invitación
        </h1>
        <p className="mt-3 text-base leading-relaxed text-[color:var(--ink-2)]">
          Estamos dando acceso a negocios poco a poco. Deja tu correo y te
          avisamos cuando haya lugar, o usa tu código si ya te invitaron.
        </p>
        <p className="mt-2 text-sm leading-relaxed text-[color:var(--muted)]">
          Mientras tanto no aceptamos suscripciones ni compras.
        </p>
        {detalle && (
          <p className="mt-1 text-sm leading-relaxed text-[color:var(--muted)]">{detalle}</p>
        )}

        <div className="mt-8">
          <ListaEsperaForm />
        </div>

        <nav
          aria-label="Documentos legales"
          className="mt-10 flex flex-wrap gap-x-6 border-t border-[color:var(--line)] pt-4 text-sm text-[color:var(--muted)]"
        >
          <Link href="/terminos-y-condiciones" className="flex min-h-11 items-center hover:text-[color:var(--ink)]">
            Términos y condiciones
          </Link>
          <Link href="/politica-de-privacidad" className="flex min-h-11 items-center hover:text-[color:var(--ink)]">
            Política de privacidad
          </Link>
        </nav>
      </div>
    </main>
  );
}
