// /app/tareas/[id] — Tarea: estado, controles, ejecuciones, aprobaciones y
// evidencia (J7.5).

import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { llamarApp } from "@/lib/app-bridge";
import { identidad, sesionApp } from "@/lib/app-sesion";
import type { DetalleTarea, Inicio } from "@/lib/app-types";
import { accionTarea } from "../../acciones";
import Aprobaciones from "../../_componentes/aprobaciones";
import ErrorCarga from "../../_componentes/error-carga";
import EstadoTarea from "../../_componentes/estado-tarea";
import FormAccion from "../../_componentes/form-accion";
import { TARJETA } from "../../_componentes/estilos";

const MOTIVOS: Record<string, string> = {
  presupuesto_agotado: "El agente agotó su presupuesto.",
  aprobacion_rechazada: "Rechazaste la operación que pidió el agente.",
  herramienta_no_permitida: "El agente pidió una herramienta que no tiene permitida.",
  proveedor_no_disponible: "El proveedor del modelo no está disponible.",
  criterios_no_cumplidos: "El responsable no dio por cumplidos los criterios.",
};

const TERMINALES = new Set(["completada", "fallida", "cancelada"]);

const ESTADOS_EJECUCION: Record<string, string> = {
  encolada: "en cola",
  en_curso: "en curso",
  esperando_aprobacion: "esperando aprobación",
  terminada: "terminada",
  fallida: "fallida",
  cancelada: "cancelada",
  abandonada: "abandonada",
};

function unidades(n: number): string {
  return `${n} ${n === 1 ? "unidad" : "unidades"}`;
}

function Control({ tareaId, operacion, texto, secundario }: {
  tareaId: number; operacion: string; texto: string; secundario?: boolean;
}) {
  return (
    <FormAccion accion={accionTarea} boton={texto} secundario={secundario} className="contents">
      <input type="hidden" name="tarea_id" value={tareaId} />
      <input type="hidden" name="operacion" value={operacion} />
    </FormAccion>
  );
}

export default async function PaginaTarea({ params }: { params: Promise<{ id: string }> }) {
  const sesion = await sesionApp();
  if (!sesion) redirect("/app/entrar");
  const { id } = await params;
  if (!/^\d{1,12}$/.test(id)) notFound();

  const [res, inicio] = await Promise.all([
    llamarApp<DetalleTarea>("tarea", { ...identidad(sesion), tarea_id: Number(id) }),
    llamarApp<Inicio>("inicio", identidad(sesion)),
  ]);
  if (!res.ok) {
    if (res.status === 404) notFound();
    return <ErrorCarga error={res.error} detalle={res.detalle} />;
  }
  const { tarea, ejecuciones, evidencias } = res.data;
  const idsEjecucion = new Set(ejecuciones.map((e) => e.id));
  const puedeEjecutar = tarea.estado === "pendiente" && tarea.asignada_a_agente_id !== null;
  const puedeReintentar = tarea.estado === "fallida" || tarea.estado === "bloqueada";
  const puedeCancelar = !TERMINALES.has(tarea.estado);
  const sinAgente = tarea.estado === "pendiente" && tarea.asignada_a_agente_id === null;
  const pendientes = inicio.ok
    ? inicio.data.aprobaciones_pendientes.filter((a) => idsEjecucion.has(a.ejecucion_id))
    : [];

  return (
    <div className="space-y-8">
      <div>
        <Link
          href={`/app/proyectos/${tarea.proyecto_id}`}
          className="text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)]"
        >
          ← Proyecto
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-medium tracking-tight">{tarea.titulo}</h1>
          <EstadoTarea estado={tarea.estado} />
        </div>
        {tarea.descripcion && (
          <p className="mt-2 whitespace-pre-wrap text-[color:var(--ink-2)]">{tarea.descripcion}</p>
        )}
        {tarea.motivo_bloqueo && (
          <p className="mt-2 text-sm text-amber-800 dark:text-amber-300">
            {MOTIVOS[tarea.motivo_bloqueo] ?? tarea.motivo_bloqueo}
          </p>
        )}
      </div>

      {(puedeEjecutar || puedeReintentar || puedeCancelar) && (
        <section aria-label="Controles" className="flex flex-wrap items-center gap-3">
          {puedeEjecutar && <Control tareaId={tarea.id} operacion="ejecutar" texto="Ejecutar" />}
          {puedeReintentar && (
            <Control tareaId={tarea.id} operacion="reintentar" texto="Reintentar" />
          )}
          {puedeCancelar && (
            <Control tareaId={tarea.id} operacion="cancelar" texto="Cancelar tarea" secundario />
          )}
          {sinAgente && (
            <p className="text-sm text-[color:var(--muted)]">
              Asigna un agente para poder ejecutarla.
            </p>
          )}
        </section>
      )}

      {pendientes.length > 0 && (
        <section aria-labelledby="t-aprobacion" className={TARJETA}>
          <h2 id="t-aprobacion" className="text-lg font-medium">
            El agente pide tu aprobación
          </h2>
          <div className="mt-4">
            <Aprobaciones items={pendientes} />
          </div>
        </section>
      )}

      <section aria-labelledby="t-evidencia" className={TARJETA}>
        <h2 id="t-evidencia" className="text-lg font-medium">
          Evidencia
        </h2>
        {evidencias.length === 0 ? (
          <p className="mt-3 text-sm text-[color:var(--muted)]">Todavía no hay evidencia.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {evidencias.map((e) => (
              <li key={e.id} className="rounded-xl border border-[color:var(--line)] p-3">
                <p className="text-xs text-[color:var(--muted)]">
                  {e.tipo} · ejecución {e.ejecucion_id} ·{" "}
                  <span title={e.hash_sha256}>sha256 {e.hash_sha256.slice(0, 12)}…</span>
                </p>
                <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words font-sans text-sm">
                  {e.contenido}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="t-ejecuciones" className={TARJETA}>
        <h2 id="t-ejecuciones" className="text-lg font-medium">
          Ejecuciones
        </h2>
        {ejecuciones.length === 0 ? (
          <p className="mt-3 text-sm text-[color:var(--muted)]">Sin ejecuciones.</p>
        ) : (
          <ul className="mt-3 divide-y divide-[color:var(--line)] text-sm">
            {ejecuciones.map((e) => (
              <li key={e.id} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2">
                <span>
                  Intento {e.intento} · {ESTADOS_EJECUCION[e.estado] ?? e.estado}
                  {e.error_codigo && (
                    <span className="text-[color:var(--muted)]"> · {e.error_codigo}</span>
                  )}
                </span>
                <span className="text-[color:var(--muted)]">{unidades(e.unidades_consumidas)}</span>
              </li>
            ))}
          </ul>
        )}
        {(tarea.estado === "en_ejecucion" || ejecuciones.some((e) => e.estado === "encolada")) && (
          <p className="mt-3 text-sm text-[color:var(--muted)]">
            El agente está trabajando. Recarga la página para ver el avance.
          </p>
        )}
      </section>
    </div>
  );
}
