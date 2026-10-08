"use client";
// Formulario genérico ligado a una server action (J7.5). Muestra el error
// que devuelve la acción, deshabilita el botón mientras se envía y solo
// vacía los campos si la acción salió bien (React 19 los vaciaría siempre
// con `action={…}`; aquí un error no debe borrar lo escrito).

import { useActionState, useEffect, useRef, startTransition } from "react";
import type { EstadoAccion } from "@/lib/app-types";
import { BOTON, BOTON_SECUNDARIO } from "./estilos";

type Accion = (prev: EstadoAccion, fd: FormData) => Promise<EstadoAccion>;

interface FormAccionProps {
  accion: Accion;
  boton: string;
  children?: React.ReactNode;
  secundario?: boolean;
  className?: string;
  /** Vacía los campos tras un envío correcto. */
  limpiar?: boolean;
}

export default function FormAccion({
  accion,
  boton,
  children,
  secundario,
  className,
  limpiar = true,
}: FormAccionProps) {
  const [estado, despachar, enviando] = useActionState(accion, {} as EstadoAccion);
  const formulario = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (limpiar && estado.ok) formulario.current?.reset();
  }, [estado, limpiar]);

  return (
    <form
      ref={formulario}
      className={className ?? "space-y-3"}
      onSubmit={(e) => {
        e.preventDefault();
        const datos = new FormData(e.currentTarget);
        startTransition(() => despachar(datos));
      }}
    >
      {children}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={enviando}
          className={secundario ? BOTON_SECUNDARIO : BOTON}
        >
          {enviando ? "Enviando…" : boton}
        </button>
        {estado.error && (
          <p role="alert" className="text-sm text-[color:var(--dato-neg)]">
            {estado.error}
          </p>
        )}
      </div>
    </form>
  );
}
