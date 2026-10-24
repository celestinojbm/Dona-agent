import {
  Calendar,
  LayoutGrid,
  Mail,
  MessageCircle,
  Smartphone,
  Table2,
  type LucideIcon,
} from "lucide-react";
import { Revelar } from "./revelar";

const CANALES: { icono: LucideIcon; titulo: string; meta: string }[] = [
  { icono: LayoutGrid, titulo: "Panel web", meta: "Principal" },
  { icono: Smartphone, titulo: "App móvil", meta: "Principal" },
  { icono: MessageCircle, titulo: "WhatsApp", meta: "Canal" },
  { icono: Mail, titulo: "Gmail", meta: "Opcional · OAuth" },
  { icono: Calendar, titulo: "Calendar", meta: "Opcional · OAuth" },
  { icono: Table2, titulo: "Sheets", meta: "Opcional · OAuth" },
];

export function Integraciones() {
  return (
    <section className="v2-integra" aria-labelledby="integra-titulo">
      <div className="v2-integra-intro">
        <p className="v2-kicker">§3 — Dónde trabaja Dona</p>
        <h2 id="integra-titulo">Donde ya está tu negocio.</h2>
        <p>
          App y panel web primero. WhatsApp como canal más. Google solo si tú lo
          conectas, y siempre con el patrón preparar → confirmar.
        </p>
      </div>
      <div className="v2-integra-grid">
        {CANALES.map((canal, indice) => {
          const Icono = canal.icono;
          return (
            <Revelar key={canal.titulo} orden={indice} className="v2-integra-item">
              <span className="v2-icono-caja">
                <Icono size={22} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <h3>{canal.titulo}</h3>
              <p>{canal.meta}</p>
            </Revelar>
          );
        })}
      </div>
    </section>
  );
}
