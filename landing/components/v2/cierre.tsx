import Link from "next/link";
import { MENSAJE_PAUSA } from "@/lib/pausa";
import { Boton } from "./boton";
import { Logo } from "./logo";

export function Cierre() {
  return (
    <>
      <section id="acceso" className="v2-cta v2-grano" aria-labelledby="cierre-titulo">
        <p className="v2-kicker">§6 — Empieza</p>
        <h2 id="cierre-titulo">
          Tu negocio,
          <br />
          con <span className="v2-subrayado">firma</span>.
        </h2>
        <div className="v2-cta-acciones">
          <Boton href="#acceso" variante="sobre-negro" flecha className="v2-btn-hero">
            Pedir acceso a la beta
          </Boton>
          <a href="#pausa" className="v2-btn v2-btn-texto">
            Hablar con nosotros
          </a>
        </div>
        <p className="v2-cta-nota">Pedir acceso no envía tus datos. No hay registro en esta página.</p>
      </section>

      <footer id="pie" className="v2-pie">
        <div className="v2-pie-marca">
          <Link href="/" aria-label="Dona, inicio">
            <Logo tono="blanco" />
          </Link>
          <p>
            {MENSAJE_PAUSA} Estamos terminando la beta.
          </p>
        </div>
        <nav aria-label="Producto">
          <p className="v2-kicker">Producto</p>
          <a href="#como-funciona">Centro de acciones</a>
          <a href="#precios">Créditos</a>
          <a href="#seguridad">Seguridad</a>
        </nav>
        <nav aria-label="Legal">
          <p className="v2-kicker">Legal</p>
          <Link href="/politica-de-privacidad">Privacidad</Link>
          <Link href="/terminos-y-condiciones">Términos</Link>
          <Link href="/politica-de-privacidad#tus-derechos">Exportar datos</Link>
        </nav>
        <nav aria-label="Ayuda">
          <p className="v2-kicker">Ayuda</p>
          <a href="#faq-titulo">Preguntas</a>
          <a href="#pausa">Contacto</a>
        </nav>
        <div>
          <p className="v2-kicker">Estado</p>
          <p>Beta controlada</p>
        </div>
      </footer>
    </>
  );
}
