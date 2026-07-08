"use client";

// landing/app/dashboard/dashboard-client.tsx — Shell del dashboard.
//
// App-shell de dos columnas sobre el sistema claro editorial: sidebar
// izquierda con las secciones (pill negra activa, como la nav de la landing
// y el mockup del hero) + área de contenido que monta UNA sección a la vez.
// El chat es ciudadano de primera clase (sección propia, full-height).
//
// La sección activa se sincroniza con la URL (?s=chat) vía replaceState:
// deep-linking y refresh conservan dónde estabas, sin recargar la página.
// Los gates de negocio se conservan tal cual eran en la página única:
//   - inicio / créditos dependen de /api/dashboard-data (skeleton → error).
//   - acciones / oportunidades solo con suscripción no cancelada.
//   - Control Room solo para la allowlist interna (lib/control-room).
// Las secciones con fetch propio (chat, outputs, reportes) no dependen del
// load global: si dashboard-data falla, siguen disponibles.

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/ui/theme-toggle";
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
  Home,
  Lightbulb,
  Image as ImageIcon,
  BarChart3,
  LineChart,
  Activity,
  Menu,
  X,
  ArrowRight,
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
import SeccionAnalitica from "./seccion-analitica";

interface DashboardProps {
  session: { user?: { email?: string | null } };
}

type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: UsuarioResumen }
  | { status: "error"; code: string };

// ── Secciones del shell ────────────────────────────────────────────────────

const SECCIONES_VALIDAS = [
  "inicio",
  "chat",
  "acciones",
  "oportunidades",
  "analitica",
  "reportes",
  "outputs",
  "creditos",
  "integraciones",
  "control-room",
] as const;

export type SeccionId = (typeof SECCIONES_VALIDAS)[number];

function esSeccionValida(s: string | null): s is SeccionId {
  return s !== null && (SECCIONES_VALIDAS as readonly string[]).includes(s);
}

// Estados terminales de una acción (espejo de seccion-action-center.tsx):
// lo no-terminal cuenta como "pendiente" para el badge de la sidebar.
const ESTADOS_ACCION_TERMINALES = ["completed", "rejected", "failed", "cancelled"];

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
  const [seccion, setSeccion] = useState<SeccionId>("inicio");
  const [menuMovil, setMenuMovil] = useState(false);
  const [pendientes, setPendientes] = useState<number | null>(null);

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

  // Sección inicial desde la URL (?s=chat). Solo en cliente: el SSR
  // renderiza "inicio" y el efecto corrige al montar si hay deep-link.
  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get("s");
    if (esSeccionValida(s)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSeccion(s);
    }
  }, []);

  // Badge de acciones pendientes en la sidebar. Best-effort: si el
  // endpoint falla, el badge simplemente no se muestra (la sección
  // Acciones hace su propio fetch con manejo de errores completo).
  useEffect(() => {
    let cancelado = false;
    (async () => {
      try {
        const res = await fetch("/api/automation/acciones", {
          cache: "no-store",
        });
        if (!res.ok || cancelado) return;
        const data = (await res.json()) as {
          acciones?: { estado: string }[];
        };
        if (!cancelado && Array.isArray(data.acciones)) {
          setPendientes(
            data.acciones.filter(
              (a) => !ESTADOS_ACCION_TERMINALES.includes(a.estado),
            ).length,
          );
        }
      } catch {
        // badge opcional — sin acción
      }
    })();
    return () => {
      cancelado = true;
    };
  }, []);

  // Navegar a una sección: estado + URL (?s=) sin recargar + scroll arriba.
  const irA = useCallback((id: SeccionId) => {
    setSeccion(id);
    setMenuMovil(false);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("s", id);
      window.history.replaceState(null, "", url.toString());
    } catch {
      // la URL API está siempre en cliente; guard defensivo
    }
    window.scrollTo({ top: 0 });
  }, []);

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
        toast.error(
          "El portal de facturación todavía no está configurado. " +
            "Escríbenos a hola@usadona.com y te ayudamos.",
        );
      } else {
        toast.error("No pudimos abrir el portal. Intenta de nuevo en un momento.");
      }
    } catch {
      toast.error("Error de conexión. Intenta de nuevo.");
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
        toast.error(
          "Este paquete todavía no está disponible. " +
            "Escríbenos a hola@usadona.com y te ayudamos.",
        );
      } else {
        toast.error("No pudimos iniciar la compra. Intenta de nuevo en un momento.");
      }
    } catch {
      toast.error("Error de conexión. Intenta de nuevo.");
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

  // La suscripción cancelada apaga acciones/oportunidades (igual que en la
  // página única). Mientras carga, los items no se muestran todavía.
  const subCancelada =
    load.status === "ready" && load.data.suscripcion.estado === "canceled";
  const puedeOperar = load.status === "ready" && !subCancelada;

  const navPrincipal: {
    id: SeccionId;
    label: string;
    icon: typeof Home;
    badge?: number | null;
  }[] = [
    { id: "inicio", label: "Inicio", icon: Home },
    { id: "chat", label: "Chat", icon: MessageSquare },
    ...(puedeOperar
      ? [
          {
            id: "acciones" as const,
            label: "Acciones",
            icon: Zap,
            badge: pendientes,
          },
          {
            id: "oportunidades" as const,
            label: "Oportunidades",
            icon: Lightbulb,
          },
        ]
      : []),
    { id: "analitica", label: "Analítica", icon: LineChart },
    { id: "reportes", label: "Reportes", icon: BarChart3 },
    { id: "outputs", label: "Outputs", icon: ImageIcon },
    { id: "creditos", label: "Créditos y plan", icon: Wallet },
    { id: "integraciones", label: "Integraciones", icon: Link2 },
  ];

  function renderNav() {
    return (
      <nav aria-label="Secciones del dashboard" className="space-y-1">
        {navPrincipal.map((item) => {
          const Icon = item.icon;
          const activa = seccion === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => irA(item.id)}
              aria-current={activa ? "page" : undefined}
              className={`flex w-full cursor-pointer items-center gap-2.5 rounded-full px-3.5 py-2 text-sm transition-colors ${
                activa
                  ? "pill-active font-medium"
                  : "text-[color:var(--ink-2)] hover:bg-[color:var(--bg-soft)] hover:text-[color:var(--ink)]"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
              {typeof item.badge === "number" && item.badge > 0 && (
                <span
                  className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums ${
                    activa
                      ? "bg-[color:var(--bg)]/25 text-[color:var(--bg)]"
                      : "bg-[color:var(--fill)] text-[color:var(--brand-ink)]"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>
    );
  }

  function renderFooterNav() {
    return (
      <div className="space-y-4">
        {mostrarControlRoomInterno && (
          <button
            type="button"
            onClick={() => irA("control-room")}
            aria-current={seccion === "control-room" ? "page" : undefined}
            className={`flex w-full cursor-pointer items-center gap-2.5 rounded-full px-3.5 py-2 text-sm transition-colors ${
              seccion === "control-room"
                ? "pill-active font-medium"
                : "text-[color:var(--muted)] hover:bg-[color:var(--bg-soft)] hover:text-[color:var(--ink)]"
            }`}
          >
            <Activity className="h-4 w-4 shrink-0" />
            Control Room
            <span
              className={`ml-auto text-[10px] font-semibold uppercase tracking-[0.12em] ${
                seccion === "control-room" ? "text-[color:var(--bg)]/70" : "text-[color:var(--muted)]"
              }`}
            >
              interno
            </span>
          </button>
        )}
        <div className="border-t border-[color:var(--line)] px-3.5 pt-4">
          {load.status === "ready" && (
            <p className="mb-2 text-xs text-[color:var(--muted)]">
              <span className="font-semibold text-[color:var(--ink)] tabular-nums">
                {load.data.creditos.saldo_actual}
              </span>{" "}
              créditos
            </p>
          )}
          <p className="truncate text-xs text-[color:var(--muted)]">
            {session.user?.email}
          </p>
          <button
            onClick={() => signOut({ redirectTo: "/" })}
            className="mt-2 flex cursor-pointer items-center gap-1.5 text-sm text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)]"
          >
            <LogOut className="h-4 w-4" />
            Salir
          </button>
          <div className="mt-3">
            <ThemeToggle />
          </div>
        </div>
      </div>
    );
  }

  // Contenido de la sección activa, con los mismos gates que la página única.
  function renderContenido() {
    switch (seccion) {
      case "chat":
        return (
          <div className="flex h-[calc(100dvh-11.5rem)] min-h-[420px] flex-col md:h-[calc(100dvh-6.5rem)]">
            <SeccionChat fullHeight />
          </div>
        );
      case "outputs":
        return <SeccionGaleria />;
      case "reportes":
        return <SeccionReportes />;
      case "analitica":
        if (load.status === "loading") return <SeccionesSkeleton />;
        if (load.status === "error")
          return <ErrorCard code={load.code} onRetry={handleRetry} />;
        return (
          <SeccionAnalitica
            data={load.data}
            irAAcciones={() => irA("acciones")}
          />
        );
      case "integraciones":
        return <SeccionIntegraciones connections={connections} />;
      case "acciones":
        if (load.status === "loading") return <SeccionesSkeleton />;
        if (load.status === "error")
          return <ErrorCard code={load.code} onRetry={handleRetry} />;
        if (subCancelada) return <SeccionNoDisponible />;
        return <SeccionActionCenter />;
      case "oportunidades":
        if (load.status === "loading") return <SeccionesSkeleton />;
        if (load.status === "error")
          return <ErrorCard code={load.code} onRetry={handleRetry} />;
        if (subCancelada) return <SeccionNoDisponible />;
        return <SeccionOportunidades />;
      case "creditos":
        if (load.status === "loading") return <SeccionesSkeleton />;
        if (load.status === "error")
          return <ErrorCard code={load.code} onRetry={handleRetry} />;
        return (
          <div className="space-y-10">
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
          </div>
        );
      case "control-room":
        return mostrarControlRoomInterno ? (
          <SeccionControlRoom />
        ) : (
          <SeccionNoDisponible />
        );
      case "inicio":
      default:
        if (load.status === "loading") return <SeccionesSkeleton />;
        if (load.status === "error")
          return <ErrorCard code={load.code} onRetry={handleRetry} />;
        return (
          <SeccionInicio
            data={load.data}
            pendientes={pendientes}
            puedeOperar={puedeOperar}
            irA={irA}
          />
        );
    }
  }

  return (
    <div className="relative z-[2] min-h-screen bg-[color:var(--bg)] text-[color:var(--ink)]">
      {/* Topbar móvil */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[color:var(--line)] bg-[color:var(--bg)] px-4 md:hidden">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Dona
        </Link>
        <button
          type="button"
          aria-label="Menú"
          aria-expanded={menuMovil}
          onClick={() => setMenuMovil((v) => !v)}
          className="cursor-pointer text-[color:var(--ink-2)]"
        >
          {menuMovil ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {/* Drawer móvil (Radix Sheet: focus-trap, ESC, scroll-lock, foco devuelto) */}
      <Sheet open={menuMovil} onOpenChange={setMenuMovil}>
        <SheetContent
          side="left"
          aria-describedby={undefined}
          className="justify-between overflow-y-auto p-6 md:hidden"
        >
          <SheetTitle className="sr-only">Menú de navegación</SheetTitle>
          <div>
            <Link href="/" className="block px-3.5 text-xl font-semibold tracking-tight">
              Dona
            </Link>
            <div className="mt-6">{renderNav()}</div>
          </div>
          <div className="mt-8">{renderFooterNav()}</div>
        </SheetContent>
      </Sheet>

      <div className="mx-auto flex w-full max-w-[1440px]">
        {/* Sidebar desktop */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col justify-between border-r border-[color:var(--line)] px-4 py-6 md:flex">
          <div className="min-h-0 overflow-y-auto">
            <Link
              href="/"
              className="block px-3.5 text-[22px] font-semibold tracking-tight text-[color:var(--ink)]"
            >
              Dona
            </Link>
            <div className="mt-8">{renderNav()}</div>
          </div>
          {renderFooterNav()}
        </aside>

        {/* Contenido */}
        <main className="min-w-0 flex-1 px-5 py-8 md:px-10 md:py-10">
          <div className="mx-auto max-w-5xl">{renderContenido()}</div>
        </main>
      </div>

      {/* T2.0.D — Tour de primer login. Ahora navega entre secciones del
          shell paso a paso (onIrASeccion). Solo con sub activa y si no se
          marcó "visto" en localStorage. */}
      <TourDashboard
        habilitado={puedeOperar}
        onIrASeccion={(s) => {
          if (esSeccionValida(s)) irA(s);
        }}
      />
    </div>
  );
}

// ── Secciones propias del shell ────────────────────────────────────────────

/** Vista Inicio: resumen compuesto de piezas existentes + accesos rápidos. */
function SeccionInicio({
  data,
  pendientes,
  puedeOperar,
  irA,
}: {
  data: UsuarioResumen;
  pendientes: number | null;
  puedeOperar: boolean;
  irA: (s: SeccionId) => void;
}) {
  const chip = chipEstado(data.suscripcion.estado);
  const txs = data.transacciones_recientes.slice(0, 4);
  const hayPendientes = puedeOperar && pendientes !== null && pendientes > 0;

  return (
    <div className="space-y-8">
      <div>
        <p className="eyebrow mb-3">Inicio</p>
        <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--ink)]">
          {hayPendientes
            ? `Hola — ${pendientes} ${pendientes === 1 ? "acción espera" : "acciones esperan"} tu aprobación`
            : "Hola — esto es lo que pasa con tu cuenta"}
        </h1>
      </div>

      {/* Métricas rápidas: cada tarjeta navega a su sección */}
      <div className="grid gap-4 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => irA("creditos")}
          className="surface-card cursor-pointer p-6 text-left"
        >
          <p className="eyebrow mb-2">Créditos</p>
          <p className="text-4xl font-medium tabular-nums tracking-tight text-[color:var(--ink)]">
            {data.creditos.saldo_actual}
          </p>
          <p className="mt-2 flex items-center gap-1 text-xs font-medium text-[color:var(--brand-ink)]">
            Ver saldo y paquetes
            <ArrowRight className="h-3 w-3" />
          </p>
        </button>

        {puedeOperar ? (
          <button
            type="button"
            onClick={() => irA("acciones")}
            className="surface-card cursor-pointer p-6 text-left"
          >
            <p className="eyebrow mb-2">Por aprobar</p>
            <p className="text-4xl font-medium tabular-nums tracking-tight text-[color:var(--ink)]">
              {pendientes === null ? "—" : String(pendientes).padStart(2, "0")}
            </p>
            <p className="mt-2 flex items-center gap-1 text-xs font-medium text-[color:var(--brand-ink)]">
              Revisar acciones
              <ArrowRight className="h-3 w-3" />
            </p>
          </button>
        ) : (
          <Link href="/#pricing" className="surface-card block p-6 text-left">
            <p className="eyebrow mb-2">Suscripción</p>
            <p className="text-lg font-semibold text-[color:var(--ink)]">Cancelada</p>
            <p className="mt-2 flex items-center gap-1 text-xs font-medium text-[color:var(--brand-ink)]">
              Reactivar plan
              <ArrowRight className="h-3 w-3" />
            </p>
          </Link>
        )}

        <button
          type="button"
          onClick={() => irA("creditos")}
          className="surface-card cursor-pointer p-6 text-left"
        >
          <p className="eyebrow mb-2">Plan</p>
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold text-[color:var(--ink)]">
              {planNombre(data.suscripcion.plan)}
            </p>
            <span
              className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${chip.color}`}
            >
              {chip.texto}
            </span>
          </div>
          <p className="mt-2 flex items-center gap-1 text-xs font-medium text-[color:var(--brand-ink)]">
            Gestionar plan
            <ArrowRight className="h-3 w-3" />
          </p>
        </button>
      </div>

      {/* Acceso rápido al chat: input falso que abre la sección */}
      <button
        type="button"
        onClick={() => irA("chat")}
        className="surface-static flex w-full cursor-pointer items-center gap-3 px-6 py-4 text-left transition-colors hover:border-[color:var(--brand)]"
      >
        <span className="icon-badge h-10 w-10 shrink-0">
          <MessageSquare className="h-5 w-5" />
        </span>
        <span className="flex-1 text-sm text-[color:var(--muted)]">
          Escríbele a Dona como lo harías por WhatsApp…
        </span>
        <span className="btn-primary flex h-9 w-9 items-center justify-center rounded-full">
          <ArrowRight className="h-4 w-4" />
        </span>
      </button>

      {/* Últimos movimientos (preview) */}
      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="eyebrow flex items-center gap-2">
            <Receipt className="h-4 w-4" />
            Últimos movimientos
          </h2>
          <button
            type="button"
            onClick={() => irA("creditos")}
            className="cursor-pointer text-xs font-medium text-[color:var(--brand-ink)] hover:underline"
          >
            Ver todos
          </button>
        </div>
        {txs.length === 0 ? (
          <div className="surface-card p-6 text-center">
            <p className="text-sm text-[color:var(--muted)]">
              Todavía no hay movimientos. Tu primer cargo o consumo aparecerá aquí.
            </p>
          </div>
        ) : (
          <div className="surface-card overflow-hidden">
            <ul className="divide-y divide-[color:var(--line)]">
              {txs.map((t, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between gap-4 px-6 py-3.5"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-[color:var(--ink-2)]">
                      {t.razon || "Movimiento"}
                    </p>
                    <p className="mt-0.5 text-xs text-[color:var(--muted)]">
                      {formatFechaIso(t.creado)}
                    </p>
                  </div>
                  <p
                    className={`shrink-0 text-sm font-medium tabular-nums ${
                      t.delta >= 0
                        ? "text-emerald-700"
                        : "text-[color:var(--ink-2)]"
                    }`}
                  >
                    {t.delta >= 0 ? "+" : ""}
                    {t.delta}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}

/** Fallback para secciones apagadas (sub cancelada o sin permiso). */
function SeccionNoDisponible() {
  return (
    <section>
      <div className="surface-card p-8 text-center">
        <p className="text-[color:var(--ink-2)]">
          Esta sección no está disponible con tu suscripción actual.
        </p>
        <Link
          href="/#pricing"
          className="btn-primary mt-4 inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm"
        >
          Reactivar plan
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}

/** Conexiones (hardcoded por ahora; out of scope para T1.4) */
function SeccionIntegraciones({
  connections,
}: {
  connections: {
    name: string;
    icon: typeof Mail;
    connected: boolean;
    desc: string;
  }[];
}) {
  return (
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
      <section className="mt-10">
        <div className="h-4 w-32 mb-6 bg-[color:var(--fill)] rounded animate-pulse" />
        <div className="surface-card p-8 space-y-3">
          <div className="h-5 w-48 bg-[color:var(--fill)] rounded animate-pulse" />
          <div className="h-4 w-64 bg-[color:var(--fill)] rounded animate-pulse" />
        </div>
      </section>

      {/* Historial skeleton */}
      <section className="mt-10">
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
