"use client";

// landing/app/dashboard/accion-detalle.tsx
//
// Panel de detalle de una acción del Centro de acción. Cierra el flujo
// central: revisar estado y detalle → decidir (aprobar / rechazar /
// ejecutar) con confirmación explícita → consultar resultado e historial.
//
// Reutiliza los primitivos existentes (`components/ui/sheet.tsx`, Radix
// Dialog): foco atrapado, Escape, aria-modal y devolución de foco al
// cerrar vienen del primitivo; aquí solo se compone el contenido.
//
// Límite real documentado en la propia UI: la API todavía NO expone
// `GET /api/automation/acciones/:id` ni un historial de eventos por
// acción. Todo el detalle se arma con el payload de la lista y con los
// timestamps que ese payload ya trae.

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Lock,
  Play,
  XCircle,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import type { AccionAutomatizacion } from "@/lib/automation-types";
import {
  COPY_CRITICAL_FALLBACK,
  COPY_HIGH_APROBADA_FALLBACK,
  esTerminal,
  ESTADO_COLOR,
  etiquetaEstadoMostrado,
  RIESGO_COLOR,
  RIESGO_LABEL,
  resolverNextRequiredAction,
} from "@/lib/accion-decision";
import { lineaTiempoAccion, resumenResultado } from "@/lib/accion-formato";
import { PanelPreviewHigh, useConfirmacionHigh } from "./confirmacion-high";

type Decision = "aprobar" | "rechazar" | "ejecutar";

interface AccionDetalleProps {
  accion: AccionAutomatizacion | null;
  abierto: boolean;
  onOpenChange: (abierto: boolean) => void;
  enCurso: boolean;
  onAprobar: (id: number) => void;
  onRechazar: (id: number) => void;
  onEjecutar: (id: number) => void;
  onRefrescar: () => Promise<void> | void;
}

const COPY_CONFIRMACION: Record<Decision, { titulo: string; cuerpo: string }> = {
  aprobar: {
    titulo: "¿Aprobar esta acción?",
    cuerpo:
      "Aprobar habilita el siguiente paso de la acción. No envía nada al exterior por sí solo.",
  },
  rechazar: {
    titulo: "¿Rechazar esta acción?",
    cuerpo:
      "Rechazar es definitivo: la acción queda fuera del flujo activo y pasa al historial. No se puede volver atrás desde aquí.",
  },
  ejecutar: {
    titulo: "¿Ejecutar la acción?",
    cuerpo:
      "La ejecución de este control es dry-run: registra el resultado sin efecto externo real.",
  },
};

export default function AccionDetalle({
  accion,
  abierto,
  onOpenChange,
  enCurso,
  onAprobar,
  onRechazar,
  onEjecutar,
  onRefrescar,
}: AccionDetalleProps) {
  const [decisionPendiente, setDecisionPendiente] = useState<Decision | null>(null);
  const idAccion = accion?.id ?? 0;
  const high = useConfirmacionHigh(idAccion, async () => {
    setDecisionPendiente(null);
    await onRefrescar();
  });

  const decision = accion
    ? resolverNextRequiredAction(accion)
    : { next: "none" as const, motivo: "" };
  const hitos = useMemo(
    () => (accion ? lineaTiempoAccion(accion) : []),
    [accion],
  );
  const resultado = useMemo(
    () => (accion ? resumenResultado(accion.result_json) : null),
    [accion],
  );

  if (!accion) {
    // Radix exige un Root montado · sin acción no hay panel que mostrar.
    return null;
  }

  const puedeAprobar =
    decision.next === "approval_required" && accion.riesgo !== "critical";
  const puedeEjecutar = decision.next === "execute_available";
  const puedeConfirmarHigh = decision.next === "dedicated_confirmation_required";
  const bloqueoCritical =
    decision.next === "reinforced_approval_required"
      ? decision.motivo || COPY_CRITICAL_FALLBACK
      : "";
  const bloqueoHigh = puedeConfirmarHigh
    ? decision.motivo || COPY_HIGH_APROBADA_FALLBACK
    : "";
  const terminal = esTerminal(accion.estado);
  const confirmacion = decisionPendiente
    ? COPY_CONFIRMACION[decisionPendiente]
    : null;

  function ejecutarDecision(d: Decision) {
    setDecisionPendiente(null);
    if (d === "aprobar") onAprobar(idAccion);
    if (d === "rechazar") onRechazar(idAccion);
    if (d === "ejecutar") onEjecutar(idAccion);
  }

  return (
    <Sheet open={abierto} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-2xl overflow-y-auto px-6 py-6 gap-0"
      >
        <SheetTitle className="text-lg font-semibold text-[color:var(--ink)] pr-10">
          {accion.titulo}
        </SheetTitle>
        <SheetDescription className="text-sm text-[color:var(--ink-2)] mt-1">
          Detalle de la acción ·{" "}
          {etiquetaEstadoMostrado(accion.estado, decision.next)}
        </SheetDescription>

        <div className="flex flex-wrap items-center gap-2 mt-3">
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${RIESGO_COLOR[accion.riesgo]}`}
          >
            Riesgo {RIESGO_LABEL[accion.riesgo]}
          </span>
          <span
            className={`text-xs flex items-center gap-1.5 ${ESTADO_COLOR[accion.estado]}`}
          >
            <IconoEstado estado={accion.estado} />
            {etiquetaEstadoMostrado(accion.estado, decision.next)}
          </span>
          {accion.costo_creditos_estimado > 0 && (
            <span className="text-xs text-[color:var(--muted)] tabular-nums">
              ~{accion.costo_creditos_estimado} créditos
            </span>
          )}
        </div>

        {bloqueoCritical && (
          <div className="mt-4 p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
            <p className="text-xs text-[color:var(--dato-neg)] flex items-start gap-2">
              <Lock className="w-4 h-4 mt-0.5 shrink-0" />
              {bloqueoCritical}
            </p>
          </div>
        )}
        {bloqueoHigh && (
          <div className="mt-4 p-3 rounded-lg bg-orange-500/10 border border-orange-500/40">
            <p className="text-xs text-orange-700 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              {bloqueoHigh}
            </p>
          </div>
        )}

        <section className="mt-6" aria-labelledby={`detalle-${accion.id}`}>
          <h3 id={`detalle-${accion.id}`} className="eyebrow mb-3">
            Detalle
          </h3>
          <p className="text-sm text-[color:var(--ink-2)] leading-relaxed">
            {accion.descripcion}
          </p>
          {accion.razon_recomendacion && (
            <p className="text-xs text-[color:var(--muted)] mt-2 italic">
              · {accion.razon_recomendacion}
            </p>
          )}
          <dl className="grid gap-2 mt-4 text-xs sm:grid-cols-2">
            <Dato etiqueta="Tipo de acción" valor={accion.tipo_accion} />
            <Dato etiqueta="Playbook" valor={accion.playbook_id} />
            <Dato etiqueta="Oportunidad" valor={accion.opportunity_id} />
            <Dato
              etiqueta="Aprobación humana"
              valor={accion.requires_approval ? "Requerida" : "No requerida"}
            />
          </dl>
        </section>

        <section className="mt-6">
          <h3 className="eyebrow mb-3">Historial de la acción</h3>
          {hitos.length > 0 ? (
            <ol className="space-y-2">
              {hitos.map((h) => (
                <li key={h.clave} className="flex items-center gap-2 text-xs">
                  <Clock className="w-3.5 h-3.5 text-[color:var(--muted)]" />
                  <span className="text-[color:var(--muted)]">{h.etiqueta}:</span>
                  <span className="text-[color:var(--ink-2)] tabular-nums">
                    {h.valor}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs text-[color:var(--muted)]">
              Esta acción no tiene marcas de tiempo registradas todavía.
            </p>
          )}
          <p className="text-[11px] text-[color:var(--muted)] mt-3 leading-relaxed">
            Estas fechas son las que reporta la acción. La API aún no expone
            un historial de eventos por acción, así que no se muestran pasos
            intermedios.
          </p>
        </section>

        {resultado && !resultado.vacio && (
          <section className="mt-6">
            <h3 className="eyebrow mb-3">Resultado</h3>
            {resultado.filas.length > 0 ? (
              <dl className="rounded-lg bg-[color:var(--bg-soft)] border border-[color:var(--line)] divide-y divide-[color:var(--line)]">
                {resultado.filas.map((fila) => (
                  <div
                    key={fila.clave}
                    className="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:items-start sm:gap-3"
                  >
                    <dt className="text-xs text-[color:var(--muted)] sm:w-40 sm:shrink-0">
                      {fila.clave}
                    </dt>
                    <dd className="text-xs text-[color:var(--ink-2)] break-words">
                      {fila.valor}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <details>
                <summary className="cursor-pointer text-xs text-[color:var(--muted)]">
                  Ver resultado sin formato
                </summary>
                <pre className="text-xs text-[color:var(--ink-2)] font-mono whitespace-pre-wrap break-words leading-relaxed mt-2">
                  {resultado.crudo}
                </pre>
              </details>
            )}
          </section>
        )}

        {accion.error_message && (
          <section className="mt-6">
            <h3 className="eyebrow mb-3">Error registrado</h3>
            <p className="text-xs text-[color:var(--dato-neg)] p-3 rounded-lg bg-[#e64263]/10 border border-[#e64263]/40">
              {accion.error_message}
            </p>
          </section>
        )}

        <section className="mt-6">
          <h3 className="eyebrow mb-3">Decisión</h3>
          {terminal ? (
            <p className="text-xs text-[color:var(--muted)]">
              Acción cerrada · ya no admite decisiones.
            </p>
          ) : (
            <>
              {!puedeAprobar && !puedeEjecutar && !puedeConfirmarHigh && (
                <p className="text-xs text-[color:var(--muted)]">
                  No hay una decisión disponible desde este control para el
                  estado actual de la acción.
                </p>
              )}

              <PanelPreviewHigh api={high} accionId={accion.id} />

              {confirmacion && decisionPendiente && (
                <div
                  role="group"
                  aria-label={confirmacion.titulo}
                  className="mt-3 p-4 rounded-xl bg-[color:var(--bg-soft)] border border-[color:var(--line)]"
                >
                  <p className="text-sm font-medium text-[color:var(--ink)]">
                    {confirmacion.titulo}
                  </p>
                  <p className="text-xs text-[color:var(--ink-2)] mt-1 leading-relaxed">
                    {confirmacion.cuerpo}
                  </p>
                  <div className="flex items-center justify-end gap-2 mt-3">
                    <button
                      onClick={() => setDecisionPendiente(null)}
                      className="btn-ghost px-4 py-2 rounded-full text-xs"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={() => ejecutarDecision(decisionPendiente)}
                      className={
                        decisionPendiente === "rechazar"
                          ? "px-4 py-2 rounded-full text-xs flex items-center gap-1.5 bg-[#e64263]/10 border border-[#e64263]/40 text-[color:var(--dato-neg)] font-medium"
                          : "btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5"
                      }
                    >
                      {decisionPendiente === "aprobar" && "Sí, aprobar"}
                      {decisionPendiente === "rechazar" && "Sí, rechazar"}
                      {decisionPendiente === "ejecutar" && "Sí, ejecutar"}
                    </button>
                  </div>
                </div>
              )}

              {!confirmacion && (
                <div className="flex flex-wrap items-center gap-2">
                  {puedeAprobar && (
                    <>
                      <button
                        onClick={() => setDecisionPendiente("rechazar")}
                        disabled={enCurso}
                        className="btn-ghost px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Rechazar
                      </button>
                      <button
                        onClick={() => setDecisionPendiente("aprobar")}
                        disabled={enCurso}
                        className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {enCurso ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        )}
                        Aprobar
                      </button>
                    </>
                  )}
                  {puedeEjecutar && (
                    <button
                      onClick={() => setDecisionPendiente("ejecutar")}
                      disabled={enCurso}
                      className="btn-primary px-4 py-2 rounded-full text-xs flex items-center gap-1.5 disabled:opacity-50"
                    >
                      {enCurso ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      Ejecutar (dry-run)
                    </button>
                  )}
                  {puedeConfirmarHigh && !high.preview && (
                    <button
                      onClick={high.cargarPreview}
                      disabled={enCurso || high.busy}
                      className="px-4 py-2 rounded-full text-xs flex items-center gap-1.5 bg-orange-500/10 border border-orange-500/40 text-orange-700 font-medium disabled:opacity-50"
                    >
                      {high.busy ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Lock className="w-3.5 h-3.5" />
                      )}
                      Confirmar envío HIGH
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </SheetContent>
    </Sheet>
  );
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[color:var(--muted)]">{etiqueta}</dt>
      <dd className="text-[color:var(--ink-2)] break-words">{valor || "—"}</dd>
    </div>
  );
}

function IconoEstado({ estado }: { estado: AccionAutomatizacion["estado"] }) {
  switch (estado) {
    case "pending":
    case "approved":
      return <Clock className="w-3.5 h-3.5" />;
    case "needs_approval":
    case "failed":
      return <AlertTriangle className="w-3.5 h-3.5" />;
    case "running":
      return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
    case "completed":
      return <CheckCircle2 className="w-3.5 h-3.5" />;
    case "rejected":
    case "cancelled":
      return <XCircle className="w-3.5 h-3.5" />;
    default:
      return null;
  }
}
