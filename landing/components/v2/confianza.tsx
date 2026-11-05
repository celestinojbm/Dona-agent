import { Download, Fingerprint, ScrollText, WifiOff, type LucideIcon } from "lucide-react";
import { Revelar } from "./revelar";

const PILARES: { icono: LucideIcon; titulo: string; texto: string }[] = [
  {
    icono: Fingerprint,
    titulo: "Firma humana",
    texto: "MEDIO y ALTO esperan tu aprobación; CRÍTICO está bloqueado.",
  },
  {
    icono: ScrollText,
    titulo: "Registro de auditoría",
    texto: "Cada acción, su motivo, su costo y su resultado.",
  },
  {
    icono: WifiOff,
    titulo: "Fallo cerrado",
    texto: "Si algo no está claro, Dona se detiene.",
  },
  {
    icono: Download,
    titulo: "Tus datos son tuyos",
    texto: "Exporta o borra todo cuando quieras.",
  },
];

export function Confianza() {
  return (
    <section className="v2-confianza" aria-labelledby="confianza-titulo">
      <figure className="v2-cita" data-placeholder="testimonio">
        <p className="v2-kicker">§4 — Confianza</p>
        <h2 id="confianza-titulo" className="v2-sr">
          Confianza
        </h2>
        <blockquote>
          “Me propuso subir el combo. Le dije que no. No lo hizo. Eso es lo que quería de
          una IA.”
        </blockquote>
        <figcaption>
          <span className="v2-chip-ejemplo">Ejemplo</span>
          <span>— [Dueña de negocio, beta] · testimonio de ejemplo, sustituir</span>
        </figcaption>
      </figure>
      <div className="v2-confianza-lista">
        {PILARES.map((pilar, indice) => {
          const Icono = pilar.icono;
          return (
            <Revelar key={pilar.titulo} orden={indice} className="v2-confianza-item">
              <span className="v2-icono-caja">
                <Icono size={20} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <div>
                <h3>{pilar.titulo}</h3>
                <p>{pilar.texto}</p>
              </div>
            </Revelar>
          );
        })}
      </div>
    </section>
  );
}
