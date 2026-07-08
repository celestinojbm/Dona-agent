"use client";

import { useState, useEffect, useCallback } from "react";
import { signOut } from "next-auth/react";
import {
  Mail,
  Calendar,
  MessageSquare,
  CheckCircle2,
  XCircle,
  LogOut,
  CreditCard,
  Link2,
  Wallet,
  Receipt,
  AlertCircle,
  RefreshCw,
  Zap,
  Plus,
} from "lucide-react";
import Link from "next/link";
import type { UsuarioResumen } from "@/lib/dashboard-types";
import { puedeVerControlRoomInterno } from "@/lib/control-room";
import TourDashboard from "./tour";
import SeccionActionCenter from "./seccion-action-center";
import SeccionControlRoom from "./seccion-control-room";
import SeccionOportunidades from "./seccion-oportunidades";
import SeccionReportes from "./seccion-reportes";
import SeccionGaleria from "./seccion-galeria";
import SeccionChat from "./seccion-chat";

interface DashboardProps {
  session: { user?: { email?: string | null } };
}

type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: UsuarioResumen }
  | { status: "error"; code: string };

// ── Helpers de presentación (puramente UI, sin secrets) ───────────────────

function planNombre(plan: string): string {
  if (plan === "premium") return "Premium";
  if (plan === "pro") return "Pro";
  return plan || "—";
}

function formatFechaUnix(unix: number | null): string | null {
  if (!unix) return null;
  try {
    return new Date(unix * 1000).toLocaleDateString("es-MX", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

function formatFechaIso(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("es-MX", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function chipEstado(estado: string): { texto: string; color: string } {
  if (estado === "active")
    return {
      texto: "Activa",
      color:
        "bg-emerald-600/10 text-emerald-700 border-emerald-600/40",
    };
  if (estado === "past_due")
    return {
      texto: "Pago atrasado",
      color: "bg-amber-500/15 text-amber-700 border-amber-500/40",
    };
  if (estado === "canceled")
    return {
      texto: "Cancelada",
      color: "bg-[#e64263]/10 text-[#e64263] border-[#e64263]/40",
    };
  return {
    texto: estado || "—",
    color: "bg-[color:var(--bg-soft)] text-[color:var(--muted)] border-[color:var(--line)]",
  };
}

function mensajeError(code: string): string {
  switch (code) {
    case "subscription_not_found":
      return "No encontramos tu suscripción. Si crees que es un error, escríbenos.";
    case "backend_timeout":
      return "El backend no respondió a tiempo. Intenta de nuevo en un momento.";
    case "backend_auth_error":
      return "Hay un problema de configuración en el servidor. Ya estamos al tanto.";
    case "network_error":
      return "Sin conexión. Verifica tu internet e intenta de nuevo.";
    default:
      return "No pudimos cargar tus datos. Intenta de nuevo.";
  }
}

// ── Componente principal ─────────────────────────────────────────────────

// T1.7 — Paquetes de top-up (deben coincidir con landing/lib/stripe.ts).
// Solo display; el priceId real lo resuelve el server. Si un priceId no
// está configurado en Vercel, el backend devuelve 503 y la UI muestra
// mensaje claro.
const TOPUP_PAQUETES = [
  { codigo: "100", creditos: 100, precio_usd: 10, sub: "Para puntuales" },
  { codigo: "500", creditos: 500, precio_usd: 40, sub: "Más conveniente" },
  { codigo: "2000", creditos: 2000, precio_usd: 120, sub: "Uso intensivo" },
] as const;


export default function DashboardClient({ session }: DashboardProps) {
  const mostrarControlRoomInterno = puedeVerControlRoomInterno(
    session.user?.email,
  );
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [openingPortal, setOpeningPortal] = useState(false);
  const [comprandoTopup, setComprandoTopup] = useState<string | null>(null);

  // Fetch puro (solo setea al final). El "loading" inicial viene del
  // useState; el retry lo dispara explícitamente vía handleRetry.
  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch("/api/dashboard-data", {
        cache: "no-store",
      });
      if (!res.ok) {
        let code = `error_${res.status}`;
        try {
          const errJson = (await res.json()) as { error?: string };
          if (errJson.error) code = errJson.error;
        } catch {
          // ignore parse error
        }
        setLoad({ status: "error", code });
        return;
      }
      const data = (await res.json()) as UsuarioResumen;
      setLoad({ status: "ready", data });
    } catch {
      setLoad({ status: "error", code: "network_error" });
    }
  }, []);

  const handleRetry = useCallback(() => {
    setLoad({ status: "loading" });
    void fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    // Fetch al mount. La regla react-hooks/set-state-in-effect (Next 16)
    // desaconseja setState en effects para promover Suspense/use(promise);
    // ese patrón requiere refactor a Server Component, fuera de scope de
    // T1.4.E. El fetch es asíncrono y el setState ocurre tras await, no
    // hay riesgo de cascade render síncrono.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchDashboard();
  }, [fetchDashboard]);

  // T1.5 — Abre Stripe Customer Portal en una pestaña del navegador.
  // El portal es la fuente canónica para cambiar método de pago,
  // descargar facturas, pausar / cancelar / reactivar la suscripción.
  // Reemplaza al flow custom de cancelación (T1.4.F sigue como
  // endpoint legacy disponible para callers programáticos).
  async function handleManageBilling() {
    setOpeningPortal(true);
    try {
      const res = await fetch("/api/billing-portal", { method: "POST" });
      const data = (await res.json()) as { url?: string; error?: string };
      if (res.ok && data.url) {
        window.location.href = data.url;
        // No reseteamos openingPortal: la página ya está navegando.
        return;
      }
      if (data.error === "portal_not_configured") {
        alert(
          "El portal de facturación todavía no está configurado. " +
            "Escríbenos a hola@usadona.com y te ayudamos.",
        );
      } else {
        alert("No pudimos abrir el portal. Intenta de nuevo en un momento.");
      }
    } catch {
      alert("Error de conexión. Intenta de nuevo.");
    }
    setOpeningPortal(false);
  }

  // T1.7 — Top-ups de créditos (compra one-time sin afectar suscripción).
  // POST /api/checkout con kind=topup → Stripe Checkout mode=payment.
  // El backend recibe el webhook checkout.session.completed mode=payment
  // y acredita vía procesar_evento_stripe (legacy path) por
  // metadata.creditos. Idempotente por stripe_session_id.
  async function handleTopup(codigo: string) {
    setComprandoTopup(codigo);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "topup", paquete: codigo }),
      });
      const data = (await res.json()) as { url?: string; error?: string };
      if (res.ok && data.url) {
        window.location.href = data.url;
        return;
      }
      if (data.error === "paquete_no_configurado") {
        alert(
          "Este paquete todavía no está disponible. " +
            "Escríbenos a hola@usadona.com y te ayudamos.",
        );
      } else {
        alert("No pudimos iniciar la compra. Intenta de nuevo en un momento.");
      }
    } catch {
      alert("Error de conexión. Intenta de nuevo.");
    }
    setComprandoTopup(null);
  }

  const connections = [
    {
      name: "Gmail",
      icon: Mail,
      connected: false,
      desc: "Conecta tu correo para que Dona lea y responda emails",
    },
    {
      name: "Google Calendar",
      icon: Calendar,
      connected: false,
      desc: "Sincroniza tu calendario para agendar y gestionar eventos",
    },
    {
      name: "WhatsApp",
      icon: MessageSquare,
      connected: true,
      desc: "Tu numero de WhatsApp vinculado con Dona",
    },
  ];

  return (
    <div className="relative z-[2] min-h-screen bg-[color:var(--bg)] text-[color:var(--ink)]">
      {/* Header */}
      <header className="border-b border-[color:var(--line)]">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-semibold text-[color:var(--ink)]">
            Dona
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-[color:var(--muted)]">
              {session.user?.email}
            </span>
            <button
              onClick={() => signOut({ redirectTo: "/" })}
              className="flex items-center gap-1.5 text-sm text-[color:var(--muted)] hover:text-[color:var(--ink)] transition-colors cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-12 space-y-10">
        {/* Saldo + Suscripción + Historial dependen de dashboard-data */}
        {load.status === "loading" && <SeccionesSkeleton />}

        {load.status === "error" && (
          <ErrorCard code={load.code} onRetry={handleRetry} />
        )}

        {load.status === "ready" && (
          <>
            <SeccionSaldo data={load.data} />
            <SeccionSuscripcion
              data={load.data}
              openingPortal={openingPortal}
              onManageBilling={handleManageBilling}
            />
            <SeccionTopups
              comprando={comprandoTopup}
              onComprar={handleTopup}
            />
            <SeccionHistorial data={load.data} />
            {/* Chat con Dona (Fase 1) · paridad total con WhatsApp. El
                usuario habla con Dona desde la web y tiene TODAS las
                herramientas (incluidas pagadas y envíos), pasando por LOS
                MISMOS gates que WhatsApp (el backend reusa generar_respuesta).
                Se muestra siempre que haya datos, incluso con sub cancelada:
                los gates de cobro deciden qué puede ejecutar según su saldo. */}
            <SeccionChat />
            {/* Oportunidades detectadas · el eslabón diagnóstico→
                oportunidad del core loop, antes del Action Center.
                Solo lectura: detectar es gratis; convertir en acciones
                vive en "Generar acciones" del Action Center. */}
            {load.data.suscripcion.estado !== "canceled" && (
              <SeccionOportunidades />
            )}
            {/* T2.1.B — Action Center. Acciones generadas por el
                Automation Core (T2.1.A). Lista, aprueba, rechaza y
                ejecuta dry-run. Solo se muestra si la sub está activa
                (canceled no genera acciones nuevas). */}
            {load.data.suscripcion.estado !== "canceled" && (
              <SeccionActionCenter />
            )}
            {/* Reportes / Medición (Fase 1) · los números de negocio del
                usuario (ventas, gastos, utilidad, pedidos, top categorías)
                que hoy sólo obtiene por WhatsApp. Solo lectura. Se muestra
                siempre, incluso con sub cancelada: son sus datos históricos.
                Empty state con gracia si aún no capturó nada por WhatsApp. */}
            <SeccionReportes />
            {/* Galería de Activos (Fase 1) · lo que Dona ya generó para el
                usuario (imágenes, videos, docs), visible en web. Solo
                lectura. Se muestra siempre, incluso con sub cancelada: los
                activos ya generados siguen siendo del usuario. */}
            <SeccionGaleria />
            {/* Control Room interno · progreso del proyecto y orquestacion
                de agentes. Datos estaticos curados en este MVP; no llama
                APIs externas ni reemplaza el Action Center operativo. */}
            {mostrarControlRoomInterno && <SeccionControlRoom />}
            {/* T2.0.D — Tour de primer login. Solo se muestra si la sub
                está activa y el usuario aún no marcó "visto" en
                localStorage. No bloquea ni reemplaza el contenido del
                dashboard si el usuario lo cierra. */}
            <TourDashboard
              habilitado={load.data.suscripcion.estado !== "canceled"}
            />
          </>
        )}

        {/* Conexiones (hardcoded por ahora; out of scope para T1.4) */}
        <section>
          <h2 className="eyebrow mb-6 flex items-center gap-2">
            <Link2 className="w-4 h-4" />
            Conexiones
          </h2>

          <div className="space-y-4">
            {connections.map((conn) => {
              const Icon = conn.icon;
              return (
                <div
                  key={conn.name}
                  className="surface-card px-6 py-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="icon-badge w-10 h-10">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-[color:var(--ink)]">
                          {conn.name}
                        </span>
                        {conn.connected ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-600/10 text-emerald-700 font-medium">
                            Conectado
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[color:var(--bg-soft)] border border-[color:var(--line)] text-[color:var(--muted)] font-medium">
                            Desconectado
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[color:var(--muted)] mt-0.5">
                        {conn.desc}
                      </p>
                    </div>
                  </div>

                  <button
                    className={`text-sm px-5 py-2 rounded-full ${
                      conn.connected
                        ? "btn-ghost"
                        : "btn-primary"
                    }`}
                  >
                    {conn.connected ? "Desconectar" : "Conectar"}
                  </button>
                </div>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}

// ── Subcomponentes ─────────────────────────────────────────────────────────

function SeccionSaldo({ data }: { data: UsuarioResumen }) {
  const { saldo_actual, creditos_mensuales } = data.creditos;
  return (
    <section>
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <Wallet className="w-4 h-4" />
        Créditos
      </h2>

      <div className="surface-card p-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <p className="eyebrow mb-2">
              Saldo actual
            </p>
            <div className="flex items-end gap-3">
              <span className="text-6xl font-medium text-[color:var(--ink)] tabular-nums tracking-tight">
                {saldo_actual}
              </span>
              <span className="text-[color:var(--muted)] pb-2">créditos</span>
            </div>
          </div>
          <div className="text-left md:text-right">
            <p className="eyebrow mb-2">
              Plan mensual
            </p>
            <p className="text-[color:var(--ink-2)]">
              <span className="text-2xl text-[color:var(--ink)] font-medium tabular-nums">
                +{creditos_mensuales}
              </span>{" "}
              cada renovación
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function SeccionSuscripcion({
  data,
  openingPortal,
  onManageBilling,
}: {
  data: UsuarioResumen;
  openingPortal: boolean;
  onManageBilling: () => void;
}) {
  const { plan, estado, current_period_end, cancel_at_period_end } =
    data.suscripcion;
  const chip = chipEstado(estado);
  const fechaRenovacion = formatFechaUnix(current_period_end);

  return (
    <section>
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <CreditCard className="w-4 h-4" />
        Suscripción
      </h2>

      <div className="surface-card p-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold text-[color:var(--ink)]">
                Plan {planNombre(plan)}
              </span>
              <span
                className={`text-xs px-2.5 py-1 rounded-full border font-medium ${chip.color}`}
              >
                {chip.texto}
              </span>
            </div>

            {cancel_at_period_end && fechaRenovacion ? (
              <p className="flex items-center gap-2 text-sm text-amber-700">
                <AlertCircle className="w-4 h-4" />
                Se cancela el {fechaRenovacion}
              </p>
            ) : estado === "active" && fechaRenovacion ? (
              <p className="flex items-center gap-2 text-sm text-[color:var(--muted)]">
                <CheckCircle2 className="w-4 h-4 text-[color:var(--muted)]" />
                Próxima renovación: {fechaRenovacion}
              </p>
            ) : estado === "canceled" ? (
              <p className="flex items-center gap-2 text-sm text-[color:var(--muted)]">
                <XCircle className="w-4 h-4 text-[color:var(--muted)]" />
                Suscripción cancelada — los créditos siguen disponibles
              </p>
            ) : null}

            {estado !== "canceled" && (
              <p className="text-xs text-[color:var(--muted)] max-w-md">
                Cambia método de pago, descarga facturas, pausa, cancela o
                reactiva tu plan desde el portal de facturación.
              </p>
            )}
          </div>

          {estado === "canceled" ? (
            <Link
              href="/#pricing"
              className="btn-primary px-6 py-3 rounded-full text-sm text-center"
            >
              Reactivar plan
            </Link>
          ) : (
            <button
              onClick={onManageBilling}
              disabled={openingPortal}
              className="btn-ghost px-6 py-3 rounded-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {openingPortal ? "Abriendo..." : "Gestionar facturación"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

function SeccionTopups({
  comprando,
  onComprar,
}: {
  comprando: string | null;
  onComprar: (codigo: string) => void;
}) {
  return (
    <section>
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <Zap className="w-4 h-4" />
        Comprar créditos extra
      </h2>

      <div className="grid md:grid-cols-3 gap-4">
        {TOPUP_PAQUETES.map((p) => {
          const isLoading = comprando === p.codigo;
          const isDisabled = comprando !== null && comprando !== p.codigo;
          return (
            <button
              key={p.codigo}
              onClick={() => onComprar(p.codigo)}
              disabled={isDisabled || isLoading}
              className="surface-card p-6 text-left disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="eyebrow mb-1">
                    Paquete {p.codigo}
                  </p>
                  <p className="text-3xl font-medium text-[color:var(--ink)] tabular-nums tracking-tight">
                    {p.creditos.toLocaleString("es-MX")}
                  </p>
                  <p className="text-xs text-[color:var(--muted)] mt-1">
                    créditos · {p.sub}
                  </p>
                </div>
                <Plus className="w-5 h-5 text-[color:var(--muted)] shrink-0" />
              </div>
              <div className="flex items-center justify-between border-t border-[color:var(--line)] pt-4">
                <span className="text-lg text-[color:var(--ink)] font-medium">
                  ${p.precio_usd}
                </span>
                <span className="text-xs font-medium text-[color:var(--brand-ink)]">
                  {isLoading ? "Abriendo..." : "Comprar"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <p className="text-xs text-[color:var(--muted)] mt-4 max-w-md">
        Los créditos extra se suman a tu saldo y no expiran. Tu plan
        Premium / Pro sigue activo y se renueva normalmente.
      </p>
    </section>
  );
}


function SeccionHistorial({ data }: { data: UsuarioResumen }) {
  const txs = data.transacciones_recientes;

  return (
    <section>
      <h2 className="eyebrow mb-6 flex items-center gap-2">
        <Receipt className="w-4 h-4" />
        Movimientos recientes
      </h2>

      {txs.length === 0 ? (
        <div className="surface-card p-8 text-center">
          <p className="text-[color:var(--muted)]">
            Todavía no hay movimientos. Tu primer cargo o consumo aparecerá aquí.
          </p>
        </div>
      ) : (
        <div className="surface-card overflow-hidden">
          <ul className="divide-y divide-[color:var(--line)]">
            {txs.map((t, i) => (
              <li
                key={i}
                className="px-6 py-4 flex items-center justify-between gap-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[color:var(--ink-2)] truncate">
                    {t.razon || "Movimiento"}
                  </p>
                  <p className="text-xs text-[color:var(--muted)] mt-0.5">
                    {formatFechaIso(t.creado)}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p
                    className={`text-base tabular-nums font-medium ${
                      t.delta >= 0 ? "text-emerald-700" : "text-[color:var(--ink-2)]"
                    }`}
                  >
                    {t.delta >= 0 ? "+" : ""}
                    {t.delta}
                  </p>
                  <p className="text-xs text-[color:var(--muted)]">
                    saldo {t.saldo_resultante}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function SeccionesSkeleton() {
  return (
    <>
      {/* Saldo skeleton */}
      <section>
        <div className="h-4 w-24 mb-6 bg-[color:var(--fill)] rounded animate-pulse" />
        <div className="surface-card p-8">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
            <div className="space-y-3">
              <div className="h-3 w-24 bg-[color:var(--fill)] rounded animate-pulse" />
              <div className="h-12 w-32 bg-[color:var(--fill)] rounded animate-pulse" />
            </div>
            <div className="space-y-3">
              <div className="h-3 w-24 bg-[color:var(--fill)] rounded animate-pulse" />
              <div className="h-6 w-32 bg-[color:var(--fill)] rounded animate-pulse" />
            </div>
          </div>
        </div>
      </section>

      {/* Suscripción skeleton */}
      <section>
        <div className="h-4 w-32 mb-6 bg-[color:var(--fill)] rounded animate-pulse" />
        <div className="surface-card p-8 space-y-3">
          <div className="h-5 w-48 bg-[color:var(--fill)] rounded animate-pulse" />
          <div className="h-4 w-64 bg-[color:var(--fill)] rounded animate-pulse" />
        </div>
      </section>

      {/* Historial skeleton */}
      <section>
        <div className="h-4 w-40 mb-6 bg-[color:var(--fill)] rounded animate-pulse" />
        <div className="surface-card p-8 space-y-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-1/3 bg-[color:var(--fill)] rounded animate-pulse" />
              <div className="h-4 w-16 bg-[color:var(--fill)] rounded animate-pulse" />
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function ErrorCard({ code, onRetry }: { code: string; onRetry: () => void }) {
  return (
    <section>
      <div className="surface-card p-8" style={{ borderColor: "rgba(230, 66, 99, 0.4)" }}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-[color:var(--dato-neg)] mt-0.5 shrink-0" />
            <div>
              <p className="text-[color:var(--ink-2)]">{mensajeError(code)}</p>
              <p className="text-xs text-[color:var(--muted)] mt-1 font-mono">
                {code}
              </p>
            </div>
          </div>
          <button
            onClick={onRetry}
            className="btn-ghost px-5 py-2 rounded-full text-sm flex items-center gap-2 self-start md:self-auto"
          >
            <RefreshCw className="w-4 h-4" />
            Reintentar
          </button>
        </div>
      </div>
    </section>
  );
}
