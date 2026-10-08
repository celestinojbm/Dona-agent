// /app/registro — Alta en el piloto, solo con invitación (J7.5).

import Link from "next/link";
import { redirect } from "next/navigation";
import { sesionApp } from "@/lib/app-sesion";
import { registrar } from "../acciones";
import FormAccion from "../_componentes/form-accion";
import { CAMPO, ETIQUETA, TARJETA } from "../_componentes/estilos";

export default async function PaginaRegistro() {
  if (await sesionApp()) redirect("/app");
  return (
    <div className="mx-auto max-w-md">
      <div className={TARJETA}>
        <p className="eyebrow">Piloto por invitación</p>
        <h1 className="mt-3 text-2xl font-medium tracking-tight">Crea tu cuenta</h1>
        <p className="mt-2 text-sm text-[color:var(--muted)]">
          Usa el correo al que llegó la invitación. Se crea tu espacio con un área inicial y dos
          agentes: un responsable que revisa y un ejecutor que trabaja.
        </p>
        <FormAccion accion={registrar} boton="Crear cuenta" limpiar={false} className="mt-6 space-y-4">
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Nombre</span>
            <input name="nombre" autoComplete="name" className={CAMPO} />
          </label>
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Correo</span>
            <input name="email" type="email" autoComplete="email" required className={CAMPO} />
          </label>
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Nombre del espacio</span>
            <input name="nombre_workspace" placeholder="Mi negocio" className={CAMPO} />
          </label>
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Contraseña (mínimo 10 caracteres)</span>
            <input
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={10}
              required
              className={CAMPO}
            />
          </label>
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Repite la contraseña</span>
            <input
              name="password_confirmacion"
              type="password"
              autoComplete="new-password"
              minLength={10}
              required
              className={CAMPO}
            />
          </label>
        </FormAccion>
        <p className="mt-6 text-sm text-[color:var(--muted)]">
          ¿Ya tienes cuenta?{" "}
          <Link href="/app/entrar" className="text-[color:var(--brand-ink)] underline">
            Entra
          </Link>
        </p>
      </div>
    </div>
  );
}
