import { EscalaRiesgo } from "./escala-riesgo";
import { NIVELES } from "./datos";
import { Revelar } from "./revelar";

export function Riesgo() {
  return (
    <section id="seguridad" className="v2-riesgo" aria-labelledby="riesgo-titulo">
      <div className="v2-riesgo-intro">
        <p className="v2-kicker">§2 — Permisos por riesgo</p>
        <h2 id="riesgo-titulo">Cuanto más en juego, más control tienes.</h2>
      </div>
      <div className="v2-riesgo-filas">
        {NIVELES.map((nivel, indice) => (
          <Revelar key={nivel.id} orden={indice} className="v2-riesgo-fila">
            <span className="v2-riesgo-nivel">
              <EscalaRiesgo celdas={nivel.celdas} />
              <span>{nivel.etiqueta}</span>
            </span>
            <h3>{nivel.titulo}</h3>
            <p>{nivel.texto}</p>
          </Revelar>
        ))}
      </div>
    </section>
  );
}
