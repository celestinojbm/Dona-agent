import { PASOS } from "./datos";
import { Revelar } from "./revelar";

export function ComoFunciona() {
  return (
    <section id="como-funciona" className="v2-ciclo" aria-labelledby="como-titulo">
      <div className="v2-ciclo-intro">
        <p className="v2-kicker">§1 — Cómo funciona</p>
        <h2 id="como-titulo">Un ciclo, nueve pasos, una firma: la tuya.</h2>
      </div>
      {PASOS.map((paso, indice) => (
        <Revelar
          key={paso.id}
          orden={indice}
          className={paso.id === "05" ? "v2-paso v2-paso-permiso" : "v2-paso"}
        >
          <p className="v2-paso-num">{paso.id}</p>
          <h3>{paso.titulo}</h3>
          <p>{paso.texto}</p>
        </Revelar>
      ))}
    </section>
  );
}
