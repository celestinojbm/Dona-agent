// /app/entrar — Acceso al piloto app-first (J7.5).

import Link from "next/link";
import { redirect } from "next/navigation";
import { sesionApp } from "@/lib/app-sesion";
import { entrar } from "../acciones";
import FormAccion from "../_componentes/form-accion";
import { CAMPO, ETIQUETA, TARJETA } from "../_componentes/estilos";

export default async function PaginaEntrar() {
  if (await sesionApp()) redirect("/app");
  return (
    <div className="mx-auto max-w-md">
      <div className={TARJETA}>
        <p className="eyebrow">Piloto por invitación</p>
        <h1 className="mt-3 text-2xl font-medium tracking-tight">Entrar a Dona</h1>
        <FormAccion accion={entrar} boton="Entrar" limpiar={false} className="mt-6 space-y-4">
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Correo</span>
            <input name="email" type="email" autoComplete="email" required className={CAMPO} />
          </label>
          <label className="block space-y-1.5">
            <span className={ETIQUETA}>Contraseña</span>
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              className={CAMPO}
            />
          </label>
        </FormAccion>
        <p className="mt-6 text-sm text-[color:var(--muted)]">
          ¿Te invitaron y aún no tienes cuenta?{" "}
          <Link href="/app/registro" className="text-[color:var(--brand-ink)] underline">
            Crea tu cuenta
          </Link>
        </p>
      </div>
    </div>
  );
}
