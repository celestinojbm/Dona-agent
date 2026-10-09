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
    <main className="relative z-[2] flex min-h-screen items-center justify-center bg-[color:var(--bg)] px-6 py-16 text-[color:var(--ink)]">
      <div className="surface-static w-full max-w-lg p-10 sm:p-12">
        <p className="text-2xl font-semibold tracking-tight">Dona</p>
        <h1 className="mt-8 text-3xl font-medium tracking-tight">Página no encontrada</h1>
        <p className="mt-4 text-base leading-relaxed text-[color:var(--muted)]">
          La dirección que buscas no existe o ya no está disponible.
        </p>
        <Link
          href="/"
          className="btn-primary mt-8 inline-flex items-center rounded-full px-6 py-3 text-sm font-medium"
        >
          Volver al inicio
        </Link>
      </div>
    </main>
  );
}
