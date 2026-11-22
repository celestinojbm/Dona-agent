"use client";

// landing/components/lista-espera-form.tsx — Formularios de la lista de espera.
//
// Dos caminos, uno visible a la vez: dejar el correo, o canjear un código de
// invitación. Estados de carga, éxito y error anunciados (aria-live). No
// envía correos: el aviso queda apagado en el backend.

import { useState } from "react";
import { ArrowLeft, Check, Loader2 } from "lucide-react";

type Modo = "lista" | "invitacion";
type Estado =
  | { tipo: "inicio" }
  | { tipo: "enviando" }
  | { tipo: "hecho"; invitado: boolean }
  | { tipo: "error"; mensaje: string };

const MENSAJES_ERROR: Record<string, string> = {
  email_invalido: "Revisa el correo: no parece válido.",
  codigo_invalido: "Ese código no es válido. Revísalo o pide uno nuevo a quien te invitó.",
  demasiados_intentos: "Demasiados intentos con este correo. Espera unos minutos y vuelve a probar.",
};
const ERROR_GENERICO = "No pudimos guardar tu correo ahora mismo. Inténtalo de nuevo en un momento.";

const campo =
  "h-12 w-full rounded-xl border border-[color:var(--line)] bg-[color:var(--surface)] px-4 text-base text-[color:var(--ink)] placeholder:text-[color:var(--muted)] outline-none transition-colors focus:border-[color:var(--ink)]";
const botonPrincipal =
  "flex h-12 w-full items-center justify-center gap-2 rounded-full bg-[color:var(--ink)] px-5 text-[15px] font-medium text-[color:var(--bg)] transition-transform active:scale-[0.98] disabled:opacity-60";

export default function ListaEsperaForm() {
  const [modo, setModo] = useState<Modo>("lista");
  const [email, setEmail] = useState("");
  const [codigo, setCodigo] = useState("");
  const [empresa, setEmpresa] = useState(""); // campo trampa para bots
  const [estado, setEstado] = useState<Estado>({ tipo: "inicio" });
  const enviando = estado.tipo === "enviando";

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEstado({ tipo: "enviando" });
    const ruta = modo === "lista" ? "/api/lista-espera" : "/api/lista-espera/invitacion";
    const cuerpo = modo === "lista" ? { email, empresa } : { email, codigo };
    try {
      const res = await fetch(ruta, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      const data = (await res.json().catch(() => ({}))) as { estado?: string; error?: string };
      if (res.ok) {
        setEstado({ tipo: "hecho", invitado: data.estado === "invitado" });
        return;
      }
      setEstado({ tipo: "error", mensaje: MENSAJES_ERROR[data.error ?? ""] ?? ERROR_GENERICO });
    } catch {
      setEstado({ tipo: "error", mensaje: ERROR_GENERICO });
    }
  }

  function cambiarModo(m: Modo) {
    setModo(m);
    setEstado({ tipo: "inicio" });
  }

  if (estado.tipo === "hecho") {
    return (
      <div role="status" aria-live="polite" className="rounded-2xl bg-[color:var(--surface)] p-5">
        <span className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-emerald-600/10 text-emerald-700">
          <Check className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="text-base font-semibold text-[color:var(--ink)]">
          {estado.invitado ? "Invitación aceptada" : "Ya estás en la lista"}
        </p>
        <p className="mt-1 text-sm leading-relaxed text-[color:var(--ink-2)]">
          {estado.invitado
            ? "Tu lugar queda reservado con este correo. Te avisaremos cuando tu acceso esté listo."
            : "Guardamos tu correo. Te avisaremos cuando haya lugar para tu negocio."}
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={enviar} noValidate={false} className="space-y-3" aria-describedby="lista-espera-privacidad">
      {modo === "invitacion" && (
        <button
          type="button"
          onClick={() => cambiarModo("lista")}
          className="-ml-2 flex min-h-11 items-center gap-1.5 px-2 text-sm text-[color:var(--ink-2)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Volver a la lista de espera
        </button>
      )}

      <div>
        <label htmlFor="lista-email" className="mb-1.5 block text-sm font-medium text-[color:var(--ink)]">
          Correo
        </label>
        <input
          id="lista-email"
          type="email"
          inputMode="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="tu@negocio.com"
          className={campo}
        />
      </div>

      {modo === "invitacion" && (
        <div>
          <label htmlFor="lista-codigo" className="mb-1.5 block text-sm font-medium text-[color:var(--ink)]">
            Código de invitación
          </label>
          <input
            id="lista-codigo"
            type="text"
            autoComplete="one-time-code"
            autoCapitalize="characters"
            spellCheck={false}
            required
            minLength={8}
            maxLength={64}
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            placeholder="DONA-XXXX-XXXX"
            className={`${campo} uppercase tracking-wide`}
          />
        </div>
      )}

      {/* Campo trampa: invisible para personas, los bots lo rellenan. */}
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label htmlFor="lista-empresa">Empresa</label>
        <input
          id="lista-empresa"
          type="text"
          tabIndex={-1}
          autoComplete="off"
          value={empresa}
          onChange={(e) => setEmpresa(e.target.value)}
        />
      </div>

      {estado.tipo === "error" && (
        <p role="alert" className="text-sm text-[color:var(--dato-neg)]">
          {estado.mensaje}
        </p>
      )}

      <button type="submit" disabled={enviando} className={botonPrincipal}>
        {enviando && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {modo === "lista" ? "Unirme a la lista" : "Usar invitación"}
      </button>

      {modo === "lista" && (
        <button
          type="button"
          onClick={() => cambiarModo("invitacion")}
          className="flex h-12 w-full items-center justify-center rounded-full border border-[color:var(--line)] bg-[color:var(--surface)] text-[15px] font-medium text-[color:var(--ink)] transition-transform active:scale-[0.98]"
        >
          Tengo un código de invitación
        </button>
      )}

      <p id="lista-espera-privacidad" className="pt-1 text-xs leading-relaxed text-[color:var(--muted)]">
        Solo usamos tu correo para avisarte de tu acceso.
      </p>
    </form>
  );
}
