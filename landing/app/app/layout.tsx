// landing/app/app/layout.tsx — Shell del piloto app-first (J7.5).
//
// Si el piloto no está habilitado, todo /app es 404. Sin indexación: es un
// piloto por invitación, no una página pública.

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { appPilotoHabilitado } from "@/lib/app-piloto";
import { sesionApp } from "@/lib/app-sesion";
import { salir } from "./acciones";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Dona · piloto",
  robots: { index: false, follow: false },
};

export default async function LayoutApp({ children }: { children: React.ReactNode }) {
  if (!appPilotoHabilitado()) notFound();
  const sesion = await sesionApp();
  return (
    <div className="relative z-[2] min-h-screen bg-[color:var(--bg)] text-[color:var(--ink)]">
      <header className="border-b border-[color:var(--line)] bg-[color:var(--surface)]">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link href="/app" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            Dona
            <span className="rounded-full border border-[color:var(--line)] px-2 py-0.5 text-xs font-medium text-[color:var(--muted)]">
              piloto
            </span>
          </Link>
          {sesion && (
            <form action={salir}>
              <button type="submit" className="text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)]">
                Salir
              </button>
            </form>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-10">{children}</main>
      <footer className="mx-auto max-w-5xl px-4 pb-10 text-xs text-[color:var(--muted)] sm:px-6">
        Piloto con proveedor simulado: los agentes no llaman modelos reales, no envían mensajes
        ni cobran nada. Las operaciones reservadas esperan tu aprobación.
      </footer>
    </div>
  );
}
