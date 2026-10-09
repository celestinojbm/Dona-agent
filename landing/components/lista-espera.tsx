"use client";
// landing/components/lista-espera.tsx — Formulario "Avísame" (plazas completas).
//
// Pide correo (obligatorio) y teléfono (opcional) y los envía a
// POST /api/waitlist. Incluye un campo trampa oculto ("empresa") para bots.

import Link from "next/link";
import { useState, type FormEvent } from "react";

type Estado = "inicial" | "enviando" | "listo" | "error";

export const TEXTO_EXITO = "Listo. Te avisaremos cuando haya plazas.";
export const TEXTO_ERROR = "No pudimos registrar tu correo. Inténtalo de nuevo.";

export default function ListaEspera() {
  const [estado, setEstado] = useState<Estado>("inicial");

  async function enviar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setEstado("enviando");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(form.get("email") ?? ""),
          phone: String(form.get("phone") ?? ""),
          empresa: String(form.get("empresa") ?? ""),
        }),
      });
      setEstado(res.ok ? "listo" : "error");
    } catch {
      setEstado("error");
    }
  }

  if (estado === "listo") {
    return (
      <p role="status" className="mt-8 text-base leading-relaxed text-[color:var(--ink)]">
        {TEXTO_EXITO}
      </p>
    );
  }

  const campo =
    "w-full rounded-full border border-[color:var(--line)] bg-transparent px-5 py-3 text-sm text-[color:var(--ink)] placeholder:text-[color:var(--muted)] focus:outline-none focus:ring-2 focus:ring-[color:var(--ink)]/20";

  return (
    <form onSubmit={enviar} className="mt-8 space-y-3" aria-label="Lista de espera">
      <label htmlFor="lista-email" className="sr-only">
        Tu correo
      </label>
      <input
        id="lista-email"
        name="email"
        type="email"
        required
        maxLength={254}
        autoComplete="email"
        placeholder="Tu correo"
        className={campo}
      />
      <label htmlFor="lista-telefono" className="sr-only">
        Tu teléfono (opcional)
      </label>
      <input
        id="lista-telefono"
        name="phone"
        type="tel"
        maxLength={32}
        autoComplete="tel"
        placeholder="Tu teléfono (opcional)"
        className={campo}
      />
      {/* Campo trampa para bots: oculto a personas y lectores de pantalla. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label htmlFor="lista-empresa">Empresa</label>
        <input id="lista-empresa" name="empresa" type="text" tabIndex={-1} autoComplete="off" />
      </div>
      <button
        type="submit"
        disabled={estado === "enviando"}
        className="btn-primary inline-flex items-center rounded-full px-6 py-3 text-sm font-medium disabled:opacity-60"
      >
        Avísame
      </button>
      <p className="text-xs leading-relaxed text-[color:var(--muted)]">
        Te escribiremos solo para avisarte cuando haya plazas.{" "}
        <Link href="/politica-de-privacidad" className="underline hover:text-[color:var(--ink)]">
          Privacidad
        </Link>
      </p>
      {estado === "error" && (
        <p role="alert" className="text-sm text-[color:var(--ink)]">
          {TEXTO_ERROR}
        </p>
      )}
    </form>
  );
}
