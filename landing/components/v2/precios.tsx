import { Check } from "lucide-react";
import { Boton } from "./boton";

const PLANES = [
  {
    kicker: "Prueba",
    precio: "0",
    meta: "créditos incluidos: 20",
    puntos: ["Diagnóstico inicial", "Acciones de riesgo bajo", "Panel y app"],
    cta: "Pedir acceso",
    href: "#acceso",
    variante: "secundario" as const,
    destacado: false,
  },
  {
    kicker: "Negocio",
    precio: "$29",
    meta: "/mes · 300 créditos",
    puntos: [
      "Todo lo de Prueba",
      "Aprobación de MEDIO y ALTO",
      "Integraciones Google",
      "Reportes semanales",
    ],
    cta: "Pedir acceso",
    href: "#acceso",
    variante: "sobre-negro" as const,
    destacado: true,
  },
  {
    kicker: "Recarga",
    precio: "$10",
    meta: "100 créditos · no caducan",
    puntos: ["Créditos enteros", "Reserva antes de cobrar", "Reembolso si falla"],
    cta: "Ver recargas",
    href: "#acceso",
    variante: "secundario" as const,
    destacado: false,
  },
];

export function Precios() {
  return (
    <section id="precios" className="v2-precios" aria-labelledby="precios-titulo" data-placeholder="precios">
      <div className="v2-precios-cabecera">
        <h2 id="precios-titulo">Pagas por lo que se ejecuta.</h2>
        <div>
          <p>
            Créditos prepagos, enteros. Se reservan al proponer y se cobran solo si la
            acción se ejecuta.
          </p>
          <p className="v2-kicker v2-kicker-ejemplo">
            <span className="v2-chip-ejemplo">Ejemplo</span>
            Precios ilustrativos · Dona en pausa
          </p>
        </div>
      </div>
      <div className="v2-planes">
        {PLANES.map((plan) => (
          <article key={plan.kicker} className={plan.destacado ? "v2-plan v2-plan-destacado" : "v2-plan"}>
            <p className="v2-kicker">{plan.kicker}</p>
            <p className="v2-precio">
              <span className="v2-precio-num">{plan.precio}</span>
              <span className="v2-precio-meta">{plan.meta}</span>
            </p>
            <ul>
              {plan.puntos.map((punto) => (
                <li key={punto}>
                  <Check size={16} strokeWidth={1.5} aria-hidden="true" />
                  {punto}
                </li>
              ))}
            </ul>
            <Boton href={plan.href} variante={plan.variante} className="v2-btn-bloque">
              {plan.cta}
            </Boton>
          </article>
        ))}
      </div>
    </section>
  );
}
