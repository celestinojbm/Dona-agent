"use client";

import { useEffect, useState } from "react";
import { useMotionValueEvent, useScroll } from "framer-motion";
import { PASOS } from "./datos";

const OSCUROS = ["seguridad", "acceso"];

function pasoDesdeProgreso(valor: number) {
  // El hero abre en «permiso» (05). Al llegar al cierre queda «reporte» (09).
  return Math.min(9, Math.max(5, Math.round(5 + valor * 4)));
}

export function BarraCiclo() {
  const { scrollYProgress } = useScroll();
  const [paso, setPaso] = useState(5);
  const [oscuro, setOscuro] = useState(false);
  const [bottom, setBottom] = useState(0);

  useEffect(() => {
    const medir = () => {
      const pie = document.getElementById("pie");
      const siguiente = pie
        ? Math.max(0, Math.round(window.innerHeight - pie.getBoundingClientRect().top))
        : 0;
      const y = window.innerHeight - Math.max(24, siguiente) - 8;
      const encima = OSCUROS.some((id) => {
        const nodo = document.getElementById(id);
        if (!nodo) return false;
        const rect = nodo.getBoundingClientRect();
        return rect.top < y && rect.bottom > y;
      });
      setBottom((previo) => (previo === siguiente ? previo : siguiente));
      setOscuro((previo) => (previo === encima ? previo : encima));
    };
    medir();
    window.addEventListener("scroll", medir, { passive: true });
    window.addEventListener("resize", medir);
    return () => {
      window.removeEventListener("scroll", medir);
      window.removeEventListener("resize", medir);
    };
  }, []);

  useMotionValueEvent(scrollYProgress, "change", (valor) => {
    const siguiente = pasoDesdeProgreso(valor);
    setPaso((previo) => (previo === siguiente ? previo : siguiente));
  });

  useEffect(() => {
    setPaso(pasoDesdeProgreso(scrollYProgress.get()));
  }, [scrollYProgress]);

  return (
    <ol
      className={`v2-barra${oscuro ? " v2-barra-oscura" : ""}`}
      style={{ bottom }}
      aria-label="Ciclo de una acción"
    >
      {PASOS.map((item, indice) => (
        <li key={item.id} aria-current={indice + 1 === paso ? "step" : undefined}>
          <span>{item.id}</span> {item.nombre}
        </li>
      ))}
    </ol>
  );
}
