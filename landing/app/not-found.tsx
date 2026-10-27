// landing/app/not-found.tsx — 404 en español.
//
// Sustituye la página 404 por defecto de Next (en inglés). Rutas retiradas
// durante la pausa (/prototipo, /engineering) terminan aquí.

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Página no encontrada — Dona",
  robots: { index: false },
};

export default function NotFound() {
  return (
    <main className="tipo-landing relative z-[2] flex min-h-screen items-center justify-center bg-[color:var(--bg)] px-5 py-16 text-[color:var(--ink)] sm:px-8 sm:py-20">
      <div className="surface-static w-full max-w-3xl p-8 sm:p-12 md:p-14">
        <p className="tipo-marca font-semibold">Dona</p>
        <h1 className="tipo-hero mt-8 font-medium">Página no encontrada</h1>
        <p className="tipo-cuerpo mt-6 text-[color:var(--muted)]">
          La dirección que buscas no existe o ya no está disponible.
        </p>
        <Link
          href="/"
          className="btn-primary tipo-boton mt-10 inline-flex items-center rounded-full font-medium"
        >
          Volver al inicio
        </Link>
      </div>
    </main>
  );
}
