import { BarraCiclo } from "./barra-ciclo";
import { Cabecera } from "./cabecera";
import { Cierre } from "./cierre";
import { ComoFunciona } from "./como-funciona";
import { Confianza } from "./confianza";
import { Faq } from "./faq";
import { Hero } from "./hero";
import { Integraciones } from "./integraciones";
import { Precios } from "./precios";
import { ProveedorMovimiento } from "./proveedor-movimiento";
import { Riesgo } from "./riesgo";

export default function PaginaInicio() {
  return (
    <ProveedorMovimiento>
      <div className="dona-v2">
        <a className="v2-saltar" href="#contenido">
          Saltar al contenido
        </a>
        <Cabecera />
        <main id="contenido">
          <Hero />
          <ComoFunciona />
          <Riesgo />
          <Integraciones />
          <Confianza />
          <Precios />
          <Faq />
          <Cierre />
        </main>
        <BarraCiclo />
      </div>
    </ProveedorMovimiento>
  );
}
