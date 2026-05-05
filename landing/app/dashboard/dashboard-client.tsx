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
        "bg-emerald-500/[0.08] text-emerald-300/80 border-emerald-500/20",
    };
  if (estado === "past_due")
    return {
      texto: "Pago atrasado",
      color: "bg-amber-500/[0.08] text-amber-300/80 border-amber-500/20",
    };
  if (estado === "canceled")
    return {
      texto: "Cancelada",
      color: "bg-rose-500/[0.08] text-rose-300/80 border-rose-500/20",
    };
  return {
    texto: estado || "—",
    color: "bg-white/[0.04] text-white/40 border-white/[0.08]",
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
    <div className="min-h-screen relative z-[2]">
      {/* Header */}
      <header className="border-b border-white/[0.06] backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-normal text-white">
            Dona
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-white/40 font-light">
              {session.user?.email}
            </span>
            <button
              onClick={() => signOut({ redirectTo: "/" })}
              className="flex items-center gap-1.5 text-sm text-white/30 hover:text-white/60 transition-colors cursor-pointer"
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
          </>
        )}

        {/* Conexiones (hardcoded por ahora; out of scope para T1.4) */}
        <section>
          <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
            <Link2 className="w-4 h-4" />
            Conexiones
          </h2>

          <div className="space-y-4">
            {connections.map((conn) => {
              const Icon = conn.icon;
              return (
                <div
                  key={conn.name}
                  className="glass-card rounded-xl px-6 py-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center">
                      <Icon className="w-5 h-5 text-white/40" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-normal text-white">
                          {conn.name}
                        </span>
                        {conn.connected ? (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-white/40 font-mono">
                            Conectado
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] text-white/25 font-mono">
                            Desconectado
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-white/25 font-light mt-0.5">
                        {conn.desc}
                      </p>
                    </div>
                  </div>

                  <button
                    className={`text-sm px-5 py-2 rounded-full font-light ${
                      conn.connected
                        ? "btn-secondary text-white/40"
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
      <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
        <Wallet className="w-4 h-4" />
        Créditos
      </h2>

      <div className="glass-card rounded-2xl p-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <p className="text-xs uppercase tracking-widest text-white/35 mb-2 font-light">
              Saldo actual
            </p>
            <div className="flex items-end gap-3">
              <span className="text-6xl font-extralight text-white tabular-nums tracking-tighter">
                {saldo_actual}
              </span>
              <span className="text-white/35 font-light pb-2">créditos</span>
            </div>
          </div>
          <div className="text-left md:text-right">
            <p className="text-xs uppercase tracking-widest text-white/35 mb-2 font-light">
              Plan mensual
            </p>
            <p className="text-white/70 font-light">
              <span className="text-2xl text-white font-normal tabular-nums">
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
      <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
        <CreditCard className="w-4 h-4" />
        Suscripción
      </h2>

      <div className="glass-card rounded-2xl p-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-lg font-normal text-white">
                Plan {planNombre(plan)}
              </span>
              <span
                className={`text-xs px-2.5 py-1 rounded-full border font-mono ${chip.color}`}
              >
                {chip.texto}
              </span>
            </div>

            {cancel_at_period_end && fechaRenovacion ? (
              <p className="flex items-center gap-2 text-sm text-amber-300/70 font-light">
                <AlertCircle className="w-4 h-4" />
                Se cancela el {fechaRenovacion}
              </p>
            ) : estado === "active" && fechaRenovacion ? (
              <p className="flex items-center gap-2 text-sm text-white/35 font-light">
                <CheckCircle2 className="w-4 h-4 text-white/30" />
                Próxima renovación: {fechaRenovacion}
              </p>
            ) : estado === "canceled" ? (
              <p className="flex items-center gap-2 text-sm text-white/35 font-light">
                <XCircle className="w-4 h-4 text-white/30" />
                Suscripción cancelada — los créditos siguen disponibles
              </p>
            ) : null}

            {estado !== "canceled" && (
              <p className="text-xs text-white/30 font-light max-w-md">
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
              className="btn-secondary px-6 py-3 rounded-full text-sm disabled:opacity-50 disabled:cursor-not-allowed"
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
      <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
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
              className="glass-card rounded-2xl p-6 text-left transition-colors hover:border-white/[0.12] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-xs uppercase tracking-widest text-white/35 mb-1 font-light">
                    Paquete {p.codigo}
                  </p>
                  <p className="text-3xl font-light text-white tabular-nums tracking-tighter">
                    {p.creditos.toLocaleString("es-MX")}
                  </p>
                  <p className="text-xs text-white/35 font-light mt-1">
                    créditos · {p.sub}
                  </p>
                </div>
                <Plus className="w-5 h-5 text-white/30 shrink-0" />
              </div>
              <div className="flex items-center justify-between border-t border-white/[0.04] pt-4">
                <span className="text-lg text-white font-normal">
                  ${p.precio_usd}
                </span>
                <span className="text-xs text-white/40 font-light">
                  {isLoading ? "Abriendo..." : "Comprar"}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <p className="text-xs text-white/25 font-light mt-4 max-w-md">
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
      <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
        <Receipt className="w-4 h-4" />
        Movimientos recientes
      </h2>

      {txs.length === 0 ? (
        <div className="glass-card rounded-2xl p-8 text-center">
          <p className="text-white/35 font-light">
            Todavía no hay movimientos. Tu primer cargo o consumo aparecerá aquí.
          </p>
        </div>
      ) : (
        <div className="glass-card rounded-2xl overflow-hidden">
          <ul className="divide-y divide-white/[0.04]">
            {txs.map((t, i) => (
              <li
                key={i}
                className="px-6 py-4 flex items-center justify-between gap-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-white/70 font-light truncate">
                    {t.razon || "Movimiento"}
                  </p>
                  <p className="text-xs text-white/30 font-light mt-0.5">
                    {formatFechaIso(t.creado)}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p
                    className={`text-base tabular-nums font-normal ${
                      t.delta >= 0 ? "text-emerald-300/80" : "text-white/60"
                    }`}
                  >
                    {t.delta >= 0 ? "+" : ""}
                    {t.delta}
                  </p>
                  <p className="text-xs text-white/30 font-light">
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
        <div className="h-4 w-24 mb-6 bg-white/[0.04] rounded animate-pulse" />
        <div className="glass-card rounded-2xl p-8">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
            <div className="space-y-3">
              <div className="h-3 w-24 bg-white/[0.04] rounded animate-pulse" />
              <div className="h-12 w-32 bg-white/[0.04] rounded animate-pulse" />
            </div>
            <div className="space-y-3">
              <div className="h-3 w-24 bg-white/[0.04] rounded animate-pulse" />
              <div className="h-6 w-32 bg-white/[0.04] rounded animate-pulse" />
            </div>
          </div>
        </div>
      </section>

      {/* Suscripción skeleton */}
      <section>
        <div className="h-4 w-32 mb-6 bg-white/[0.04] rounded animate-pulse" />
        <div className="glass-card rounded-2xl p-8 space-y-3">
          <div className="h-5 w-48 bg-white/[0.04] rounded animate-pulse" />
          <div className="h-4 w-64 bg-white/[0.04] rounded animate-pulse" />
        </div>
      </section>

      {/* Historial skeleton */}
      <section>
        <div className="h-4 w-40 mb-6 bg-white/[0.04] rounded animate-pulse" />
        <div className="glass-card rounded-2xl p-8 space-y-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-1/3 bg-white/[0.04] rounded animate-pulse" />
              <div className="h-4 w-16 bg-white/[0.04] rounded animate-pulse" />
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
      <div className="glass-card rounded-2xl p-8 border-rose-500/15">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-rose-300/70 mt-0.5 shrink-0" />
            <div>
              <p className="text-white/70 font-light">{mensajeError(code)}</p>
              <p className="text-xs text-white/25 font-light mt-1 font-mono">
                {code}
              </p>
            </div>
          </div>
          <button
            onClick={onRetry}
            className="btn-secondary px-5 py-2 rounded-full text-sm flex items-center gap-2 self-start md:self-auto"
          >
            <RefreshCw className="w-4 h-4" />
            Reintentar
          </button>
        </div>
      </div>
    </section>
  );
}
