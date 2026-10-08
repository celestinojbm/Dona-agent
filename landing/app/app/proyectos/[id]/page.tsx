// /app/proyectos/[id] — Proyecto: objetivo, criterios, tareas y conversación (J7.5).

import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { llamarApp } from "@/lib/app-bridge";
import { identidad, sesionApp } from "@/lib/app-sesion";
import type { Agente, DetalleProyecto } from "@/lib/app-types";
import { agregarMensaje, crearTarea } from "../../acciones";
import ErrorCarga from "../../_componentes/error-carga";
import EstadoTarea from "../../_componentes/estado-tarea";
import FormAccion from "../../_componentes/form-accion";
import { CAMPO, ETIQUETA, TARJETA } from "../../_componentes/estilos";

export default async function PaginaProyecto({ params }: { params: Promise<{ id: string }> }) {
  const sesion = await sesionApp();
  if (!sesion) redirect("/app/entrar");
  const { id } = await params;
  if (!/^\d{1,12}$/.test(id)) notFound();

  const [res, agentes] = await Promise.all([
    llamarApp<DetalleProyecto>("proyecto", { ...identidad(sesion), proyecto_id: Number(id) }),
    llamarApp<{ agentes: Agente[] }>("agentes", identidad(sesion)),
  ]);
  if (!res.ok) {
    if (res.status === 404) notFound();
    return <ErrorCarga error={res.error} detalle={res.detalle} />;
  }
  const { proyecto, tareas, mensajes } = res.data;
  const listaAgentes = agentes.ok ? agentes.data.agentes : [];
  const nombreAgente = new Map(listaAgentes.map((a) => [a.id, a.nombre]));
  const ejecutores = listaAgentes.filter((a) => a.rol === "ejecutor");

  return (
    <div className="space-y-8">
      <div>
        <Link href="/app" className="text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)]">
          ← Inicio
        </Link>
        <h1 className="mt-3 text-3xl font-medium tracking-tight">{proyecto.nombre}</h1>
        <p className="mt-2 text-[color:var(--ink-2)]">{proyecto.objetivo}</p>
      </div>

      <section aria-labelledby="t-criterios" className={TARJETA}>
        <h2 id="t-criterios" className="text-lg font-medium">
          Criterios de aceptación
        </h2>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          El agente responsable revisa la evidencia contra estos criterios antes de dar una tarea
          por completada.
        </p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          {proyecto.criterios_aceptacion.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="t-tareas" className={TARJETA}>
        <h2 id="t-tareas" className="text-lg font-medium">
          Tareas
        </h2>
        {tareas.length === 0 ? (
          <p className="mt-3 text-sm text-[color:var(--muted)]">Sin tareas todavía.</p>
        ) : (
          <ul className="mt-3 divide-y divide-[color:var(--line)]">
            {tareas.map((t) => (
              <li key={t.id}>
                <Link
                  href={`/app/tareas/${t.id}`}
                  className="flex items-center justify-between gap-3 py-3 hover:text-[color:var(--brand-ink)]"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{t.titulo}</span>
                    <span className="block text-sm text-[color:var(--muted)]">
                      {t.asignada_a_agente_id
                        ? `Asignada a ${nombreAgente.get(t.asignada_a_agente_id) ?? "un agente"}`
                        : "Sin asignar"}
                    </span>
                  </span>
                  <EstadoTarea estado={t.estado} />
                </Link>
              </li>
            ))}
          </ul>
        )}
        {proyecto.estado === "activo" && (
          <details className="mt-4 border-t border-[color:var(--line)] pt-4">
            <summary className="cursor-pointer font-medium">Nueva tarea</summary>
            <FormAccion accion={crearTarea} boton="Crear tarea" className="mt-4 space-y-3">
              <input type="hidden" name="proyecto_id" value={proyecto.id} />
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Título</span>
                <input name="titulo" required maxLength={200} className={CAMPO} />
              </label>
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Encargo</span>
                <textarea name="descripcion" rows={3} className={CAMPO} />
              </label>
              <label className="block space-y-1.5">
                <span className={ETIQUETA}>Agente</span>
                <select name="agente_id" className={CAMPO} defaultValue={ejecutores[0]?.id ?? ""}>
                  <option value="">Sin asignar</option>
                  {ejecutores.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.nombre}
                    </option>
                  ))}
                </select>
              </label>
            </FormAccion>
          </details>
        )}
      </section>

      <section aria-labelledby="t-mensajes" className={TARJETA}>
        <h2 id="t-mensajes" className="text-lg font-medium">
          Conversación del proyecto
        </h2>
        {mensajes.length === 0 ? (
          <p className="mt-3 text-sm text-[color:var(--muted)]">Sin mensajes.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {mensajes.map((m) => (
              <li key={m.id} className="rounded-xl bg-[color:var(--bg-soft)] p-3 text-sm">
                <p className="text-xs text-[color:var(--muted)]">{m.autor_tipo}</p>
                <p className="mt-1 whitespace-pre-wrap">{m.contenido}</p>
              </li>
            ))}
          </ul>
        )}
        <FormAccion accion={agregarMensaje} boton="Enviar" className="mt-4 space-y-3">
          <input type="hidden" name="proyecto_id" value={proyecto.id} />
          <label className="block space-y-1.5">
            <span className="sr-only">Mensaje</span>
            <textarea name="contenido" required rows={2} placeholder="Escribe una nota o instrucción" className={CAMPO} />
          </label>
        </FormAccion>
      </section>
    </div>
  );
}
