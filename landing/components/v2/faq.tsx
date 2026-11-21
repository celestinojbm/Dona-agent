"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { m, useReducedMotion } from "framer-motion";
import { PREGUNTAS } from "./datos";

const FIRME = [0.2, 0, 0, 1] as const;

export function Faq() {
  const [abierta, setAbierta] = useState<string>(PREGUNTAS[0].id);
  const reducir = useReducedMotion();
  const baseId = useId();

  return (
    <section className="v2-faq" aria-labelledby="faq-titulo">
      <div className="v2-faq-intro">
        <p className="v2-kicker">§5 — Preguntas</p>
        <h2 id="faq-titulo">Lo que nos preguntan antes de dar el OK.</h2>
      </div>
      <div className="v2-faq-lista">
        {PREGUNTAS.map((item) => {
          const abierto = abierta === item.id;
          const panelId = `${baseId}-${item.id}`;
          const botonId = `${panelId}-btn`;
          return (
            <div key={item.id} id={item.id === "pausa" ? "pausa" : undefined} className="v2-faq-item">
              <button
                id={botonId}
                type="button"
                aria-expanded={abierto}
                aria-controls={panelId}
                onClick={() => setAbierta(abierto ? "" : item.id)}
              >
                <span>{item.pregunta}</span>
                <span className="v2-pm" data-abierto={abierto ? "true" : "false"} aria-hidden="true" />
              </button>
              <m.div
                id={panelId}
                role="region"
                aria-labelledby={botonId}
                aria-hidden={!abierto}
                initial={false}
                animate={{
                  height: abierto ? "auto" : 0,
                  opacity: abierto ? 1 : 0,
                }}
                transition={
                  reducir === false
                    ? { duration: 0.22, ease: FIRME }
                    : { duration: 0 }
                }
                style={{ overflow: "hidden" }}
              >
                <p>
                  {item.respuesta}
                  {item.id === "faq-datos" ? (
                    <>
                      {" "}
                      <Link href="/politica-de-privacidad#tus-derechos">Leer la política</Link>.
                    </>
                  ) : null}
                </p>
              </m.div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
