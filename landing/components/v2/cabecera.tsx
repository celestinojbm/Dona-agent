"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Logo } from "./logo";
import { Boton } from "./boton";

const ENLACES = [
  { href: "#como-funciona", texto: "Producto" },
  { href: "#seguridad", texto: "Seguridad" },
  { href: "#precios", texto: "Precios" },
] as const;

export function Cabecera() {
  const [abierto, setAbierto] = useState(false);
  const botonRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!abierto) return;
    const onKey = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") {
        setAbierto(false);
        botonRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [abierto]);

  const cerrar = () => setAbierto(false);

  return (
    <header className="v2-cabecera">
      <Link href="/" className="v2-logo-enlace" aria-label="Dona, inicio">
        <Logo />
      </Link>

      <nav className="v2-nav" aria-label="Secciones">
        {ENLACES.map((enlace) => (
          <a key={enlace.href} href={enlace.href} className="v2-nav-enlace">
            {enlace.texto}
          </a>
        ))}
        <Link href="/login" className="v2-btn v2-btn-texto">
          Entrar
        </Link>
        <Boton href="#acceso" flecha>
          Pedir acceso
        </Boton>
      </nav>

      <button
        ref={botonRef}
        type="button"
        className="v2-menu-btn"
        aria-expanded={abierto}
        aria-controls={panelId}
        onClick={() => setAbierto((valor) => !valor)}
      >
        <span className="v2-sr">{abierto ? "Cerrar menú" : "Abrir menú"}</span>
        <span className="v2-hamburguesa" data-abierto={abierto ? "true" : "false"} aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
      </button>

      {abierto ? (
        <nav id={panelId} className="v2-panel" aria-label="Secciones">
          {ENLACES.map((enlace) => (
            <a key={enlace.href} href={enlace.href} onClick={cerrar}>
              {enlace.texto}
            </a>
          ))}
          <Link href="/login" onClick={cerrar}>
            Entrar
          </Link>
          <Link href="#acceso" onClick={cerrar}>
            Pedir acceso a la beta
          </Link>
        </nav>
      ) : null}
    </header>
  );
}
