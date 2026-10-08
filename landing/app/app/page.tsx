// /app — Inicio del piloto app-first (J7.5): aprobaciones pendientes,
// áreas con sus proyectos, agentes del espacio y actividad reciente.

import Link from "next/link";
import { redirect } from "next/navigation";
import { llamarApp } from "@/lib/app-bridge";
import { identidad, sesionApp } from "@/lib/app-sesion";
import type { Agente, Inicio } from "@/lib/app-types";
import { crearArea, crearProyecto } from "./acciones";
import Aprobaciones from "./_componentes/aprobaciones";
import ErrorCarga from "./_componentes/error-carga";
import FormAccion from "./_componentes/form-accion";
import { CAMPO, ETIQUETA, TARJETA } from "./_componentes/estilos";

function fecha(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-US", { dateStyle: "medium", timeStyle: "short" });
}

export default async function PaginaInicio() {
  const sesion = await sesionApp();
  if (!sesion) redirect("/app/entrar");

  const [inicio, agentes] = await Promise.all([
    llamarApp<Inicio>("inicio", identidad(sesion)),
    llamarApp<{ agentes: Agente[] }>("agentes", identidad(sesion)),
  ]);
  if (!inicio.ok) return <ErrorCarga error={inicio.error} detalle={inicio.detalle} />;
  const { areas, proyectos, aprobaciones_pendientes, actividad } = inicio.data;

  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow">Tu espacio</p>
        <h1 className="mt-2 text-3xl font-medium tracking-tight">Inicio</h1>
      </div>

      <section aria-labelledby="t-aprobaciones" className={TARJETA}>
        <h2 id="t-aprobaciones" className="text-lg font-medium">
          Esperando tu aprobación
          {aprobaciones_pendientes.length > 0 && (
            <span className="ml-2 text-sm text-[color:var(--muted)]">
              ({aprobaciones_pendientes.length})
            </span>
          )}
        </h2>
        <div className="mt-4">
          <Aprobaciones items={aprobaciones_pendientes} />
        </div>
      </section>

      <section aria-labelledby="t-areas" className="space-y-4">
        <h2 id="t-areas" className="text-lg font-medium">
          Áreas y proyectos
        </h2>
        {areas.map((area) => {
          const suyos = proyectos.filter((p) => p.area_id === area.id);
          return (
            <div key={area.id} className={TARJETA}>
              <h3 className="font-medium">{area.nombre}</h3>
              {area.descripcion && (
                <p className="mt-1 text-sm text-[color:var(--muted)]">{area.descripcion}</p>
              )}
              {suyos.length === 0 ? (
                <p className="mt-3 text-sm text-[color:var(--muted)]">Sin proyectos todavía.</p>
              ) : (
                <ul className="mt-3 divide-y divide-[color:var(--line)]">
                  {suyos.map((p) => (
                    <li key={p.id}>
                      <Link
                        href={`/app/proyectos/${p.id}`}
                        className="flex items-center justify-between gap-3 py-3 hover:text-[color:var(--brand-ink)]"
                      >
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{p.nombre}</span>
                          <span className="block truncate text-sm text-[color:var(--muted)]">
                            {p.objetivo}
                          </span>
                        </span>
                        <span aria-hidden className="text-[color:var(--muted)]">→</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}

        <div className="grid gap-4 md:grid-cols-2">
          <details className={TARJETA}>
            <summary className="cursor-pointer font-medium">Nuevo proyecto</summary>
            <FormAccion accion={crearProyecto} boton="Crear proyecto" className="mt-4 space-y-3">
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Área</span>
                <select name="area_id" required className={CAMPO}>
                  {areas.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.nombre}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Nombre</span>
                <input name="nombre" required maxLength={200} className={CAMPO} />
              </label>
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Objetivo</span>
                <input name="objetivo" required className={CAMPO} />
              </label>
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Criterios de aceptación (uno por línea)</span>
                <textarea name="criterios" required rows={3} className={CAMPO} />
              </label>
            </FormAccion>
          </details>
          <details className={TARJETA}>
            <summary className="cursor-pointer font-medium">Nueva área</summary>
            <FormAccion accion={crearArea} boton="Crear área" className="mt-4 space-y-3">
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Nombre</span>
                <input name="nombre" required maxLength={120} className={CAMPO} />
              </label>
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Descripción</span>
                <input name="descripcion" className={CAMPO} />
              </label>
            </FormAccion>
          </details>
        </div>
      </section>

      <section aria-labelledby="t-agentes" className={TARJETA}>
        <h2 id="t-agentes" className="text-lg font-medium">
          Agentes
        </h2>
        {agentes.ok ? (
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {agentes.data.agentes.map((a) => (
              <li key={a.id} className="rounded-xl border border-[color:var(--line)] p-4">
                <p className="font-medium">
                  {a.nombre}{" "}
                  <span className="text-sm font-normal text-[color:var(--muted)]">· {a.rol}</span>
                </p>
                <p className="mt-1 text-sm text-[color:var(--muted)]">
                  Modelo: {a.modelo} · presupuesto {a.presupuesto_max_unidades} unidades
                </p>
                <p className="mt-1 text-sm text-[color:var(--muted)]">
                  Herramientas:{" "}
                  {a.herramientas_permitidas.length
                    ? a.herramientas_permitidas.join(", ").replaceAll("_", " ")
                    : "ninguna (solo revisa)"}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-[color:var(--muted)]">No se pudieron cargar los agentes.</p>
        )}
      </section>

      <section aria-labelledby="t-actividad" className={TARJETA}>
        <h2 id="t-actividad" className="text-lg font-medium">
          Actividad reciente
        </h2>
        {actividad.length === 0 ? (
          <p className="mt-3 text-sm text-[color:var(--muted)]">Sin actividad.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {actividad.map((a) => (
              <li key={a.id} className="flex flex-wrap justify-between gap-x-4">
                <span>
                  <span className="text-[color:var(--muted)]">{a.actor_tipo}</span>{" "}
                  {a.evento.replaceAll("_", " ")}
                </span>
                <time className="text-[color:var(--muted)]" dateTime={a.creado ?? undefined}>
                  {fecha(a.creado)}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
