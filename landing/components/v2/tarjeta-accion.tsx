"use client";

import { useEffect, useState } from "react";
import { Check, Fingerprint, Loader2 } from "lucide-react";
import { m, useReducedMotion } from "framer-motion";
import { EscalaRiesgo } from "./escala-riesgo";
import { Particulas } from "./particulas";

type Fase = "lista" | "press" | "aprobando" | "ejecutada";

const SELLO = { type: "spring" as const, stiffness: 600, damping: 30 };

export function TarjetaAccion() {
  const reducir = useReducedMotion();
  const [fase, setFase] = useState<Fase>("lista");
  const [pausado, setPausado] = useState(false);
  const [aviso, setAviso] = useState("");

  useEffect(() => {
    if (reducir !== false || pausado) return;
    const timers: number[] = [];
    const id = window.setInterval(() => {
      setFase("press");
      timers.push(window.setTimeout(() => setFase("aprobando"), 140));
      timers.push(window.setTimeout(() => setFase("ejecutada"), 980));
      timers.push(window.setTimeout(() => setFase("lista"), 4200));
    }, 6000);
    return () => {
      window.clearInterval(id);
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [reducir, pausado]);

  const pulsar = () => {
    setPausado(true);
    if (reducir !== false) {
      setFase("ejecutada");
      setAviso("Ejemplo marcado como ejecutado. No se envió nada.");
      return;
    }
    setFase("press");
    setAviso("Aprobando el ejemplo.");
    window.setTimeout(() => setFase("aprobando"), 140);
    window.setTimeout(() => {
      setFase("ejecutada");
      setAviso("Ejemplo marcado como ejecutado. No se envió nada.");
    }, 980);
  };

  const ocupado = fase === "aprobando";

  return (
    <div
      className="v2-hero-panel v2-grano"
      onFocus={() => setPausado(true)}
      onBlur={(evento) => {
        if (!evento.currentTarget.contains(evento.relatedTarget as Node | null)) {
          setPausado(false);
        }
      }}
    >
      <Particulas />
      <p className="v2-kicker v2-kicker-panel">Ejemplo · Acción propuesta · #A-0193</p>
      <article id="accion" className="v2-tarjeta" aria-labelledby="accion-titulo">
        <header className="v2-tarjeta-top">
          <span className="v2-tarjeta-riesgo">
            <EscalaRiesgo celdas={2} retardo={900} />
            <span>MEDIO</span>
          </span>
          <span className="v2-tarjeta-creditos">8 créditos</span>
        </header>
        <p id="accion-titulo" className="v2-maquina">
          <span>Campaña WhatsApp a 48</span>
          <span>clientes inactivos</span>
        </p>
        <p className="v2-tarjeta-base">Basado en: 3 meses sin compra · ticket medio $66</p>
        <div className="v2-tarjeta-acciones">
          <m.button
            type="button"
            className="v2-btn v2-btn-primario v2-btn-aprobar"
            animate={{ y: fase === "press" ? 1 : 0 }}
            transition={SELLO}
            aria-busy={ocupado}
            aria-describedby="accion-nota"
            onClick={pulsar}
          >
            {ocupado ? <Loader2 className="v2-gira" size={16} strokeWidth={1.5} aria-hidden="true" /> : null}
            {ocupado ? "Aprobando" : "Aprobar"}
          </m.button>
          <button
            type="button"
            className="v2-btn v2-btn-secundario"
            aria-describedby="accion-nota"
            onClick={() => {
              setPausado(true);
              setAviso("Ejemplo: editar abre el borrador. Aquí no se guarda nada.");
            }}
          >
            Editar
          </button>
        </div>
        <p id="accion-nota" className="v2-sr">
          Tarjeta de ejemplo. No envía datos ni ejecuta la acción.
        </p>
      </article>
      <div className="v2-firma-linea">
        {fase === "ejecutada" ? (
          <span className="v2-chip v2-chip-llena">
            <Check size={16} strokeWidth={1.5} aria-hidden="true" />
            Ejecutada
          </span>
        ) : (
          <span className="v2-espera">
            <Fingerprint size={16} strokeWidth={1.5} aria-hidden="true" />
            esperando tu firma
          </span>
        )}
        <p>4 créditos reservados, no cobrados</p>
      </div>
      <p className="v2-sr" aria-live="polite">
        {aviso}
      </p>
    </div>
  );
}
