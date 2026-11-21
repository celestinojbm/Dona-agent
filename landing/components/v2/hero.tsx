import { Boton } from "./boton";
import { RESUMEN_MOVIL } from "./datos";
import { TarjetaAccion } from "./tarjeta-accion";

export function Hero() {
  return (
    <section className="v2-hero" aria-labelledby="titular">
      <div className="v2-hero-copy">
        <p className="v2-kicker">
          Beta controlada
          <span className="v2-solo-escritorio"> · Para dueños de pequeños negocios</span>
        </p>
        <h1 id="titular" className="v2-h1">
          <span className="v2-linea">Tú decides.</span>
          <span className="v2-linea v2-linea-2">
            Dona <em>ejecuta.</em>
          </span>
        </h1>
        <p className="v2-lead v2-solo-escritorio">
          Dona convierte lo que sabes de tu negocio en diagnósticos, oportunidades y
          acciones reales. Nada sale sin tu permiso; todo queda medido.
        </p>
        <p className="v2-lead v2-solo-movil">
          Diagnósticos, oportunidades y acciones reales. Nada sale sin tu permiso.
        </p>
        <div className="v2-hero-acciones">
          <Boton href="#acceso" className="v2-btn-hero">
            Pedir acceso a la beta
          </Boton>
          <Boton href="#accion" variante="texto" flecha className="v2-solo-escritorio">
            Ver una acción por dentro
          </Boton>
        </div>
      </div>

      <TarjetaAccion />

      <ol className="v2-resumen-movil">
        {RESUMEN_MOVIL.map((paso) => (
          <li key={paso.id}>
            <span>{paso.id}</span>
            <div>
              <p className="v2-resumen-titulo">{paso.titulo}</p>
              <p>{paso.texto}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
