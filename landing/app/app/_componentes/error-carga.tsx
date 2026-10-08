// Bloque de error cuando el backend no responde o niega el acceso (J7.5).

import { mensajeError } from "@/lib/app-types";
import { TARJETA } from "./estilos";

export default function ErrorCarga({ error, detalle }: { error: string; detalle?: string }) {
  return (
    <div role="alert" className={TARJETA}>
      <p className="font-medium">No se pudo cargar esta vista.</p>
      <p className="mt-2 text-sm text-[color:var(--muted)]">{mensajeError(error, detalle)}</p>
    </div>
  );
}
