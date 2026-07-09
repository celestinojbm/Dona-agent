"use client";

// landing/app/checkout/checkout-client.tsx — "Configura tu plan"
//
// Página de checkout propia (referencia: el checkout de OpenAI que le gustó
// al dueño): dos columnas — izquierda "Detalles del plan" (tarjetas
// seleccionables Premium/Pro) + el formulario de pago de Stripe EMBEBIDO;
// derecha, tarjeta-resumen sticky con las funciones destacadas y el total.
// Sistema v7 (claro default, theme-aware con el modo oscuro existente).
//
// Cómo funciona el pago:
//   - Con NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY configurada: Stripe Embedded
//     Checkout. fetchClientSecret pide POST /api/checkout {plan, embedded:true}
//     (server-side crea la sesión con ui_mode "embedded_page") y Stripe monta
//     su formulario (tarjeta, wallets, email) DENTRO de esta página vía
//     createEmbeddedCheckoutPage. Al completar, Stripe redirige a
//     /success?session_id=... — mismo return que el flujo hospedado, mismo
//     webhook, mismo fulfillment.
//   - SIN la env (fallback): botón "Continuar al pago seguro" que usa el flujo
//     hospedado de siempre (POST → session.url → redirect). Así la página
//     nunca deja de vender aunque falte configurar la key en Vercel.
//
// Cambiar de plan destruye la instancia embebida y crea una sesión nueva (las
// sesiones de Checkout son inmutables por diseño de Stripe).

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Check, Loader2, Lock } from "lucide-react";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import {
  PLANES_DISPLAY,
  esPlanValido,
  type PlanCheckout,
} from "@/lib/planes";

const PK = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;

// Una sola carga de Stripe.js por página (recomendación oficial). null si la
// key no está configurada → la página opera en modo fallback hospedado.
let stripePromise: Promise<Stripe | null> | null = null;
function obtenerStripe(): Promise<Stripe | null> {
  if (!PK) return Promise.resolve(null);
  if (!stripePromise) stripePromise = loadStripe(PK);
  return stripePromise;
}

/** Crea la sesión embebida server-side y devuelve su client secret. */
async function pedirClientSecret(plan: PlanCheckout): Promise<string> {
  const res = await fetch("/api/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan, embedded: true }),
  });
  const data = (await res.json()) as { clientSecret?: string; error?: string };
  if (!res.ok || !data.clientSecret) {
    throw new Error(data.error || "checkout_failed");
  }
  return data.clientSecret;
}

export default function CheckoutClient() {
  const searchParams = useSearchParams();
  const planParam = searchParams.get("plan");
  const [plan, setPlan] = useState<PlanCheckout>(
    esPlanValido(planParam) ? planParam : "pro",
  );
  // Estado del área de pago embebida.
  const [montando, setMontando] = useState(Boolean(PK));
  const [errorPago, setErrorPago] = useState(false);
  // Estado del fallback hospedado (sin PK o si el embebido falló).
  const [redirigiendo, setRedirigiendo] = useState(false);
  const [errorHosted, setErrorHosted] = useState<string | null>(null);

  const mountRef = useRef<HTMLDivElement | null>(null);

  const planInfo =
    PLANES_DISPLAY.find((p) => p.plan === plan) ?? PLANES_DISPLAY[1];

  // Monta (y re-monta al cambiar de plan) el Embedded Checkout. La instancia
  // anterior SIEMPRE se destruye en el cleanup: sesiones de Stripe son
  // inmutables, cambiar de plan = sesión nueva.
  useEffect(() => {
    if (!PK) return;
    let cancelado = false;
    let instancia: { destroy: () => void } | null = null;

    async function montar() {
      setMontando(true);
      setErrorPago(false);
      try {
        const stripe = await obtenerStripe();
        if (!stripe) throw new Error("stripe_js_no_cargo");
        const checkout = await stripe.createEmbeddedCheckoutPage({
          fetchClientSecret: () => pedirClientSecret(plan),
        });
        if (cancelado || !mountRef.current) {
          checkout.destroy();
          return;
        }
        instancia = checkout;
        checkout.mount(mountRef.current);
      } catch {
        if (!cancelado) setErrorPago(true);
      } finally {
        if (!cancelado) setMontando(false);
      }
    }

    void montar();
    return () => {
      cancelado = true;
      instancia?.destroy();
    };
  }, [plan]);

  // Fallback hospedado: el flujo de siempre (POST → session.url → redirect).
  const irAPagoHospedado = useCallback(async () => {
    setRedirigiendo(true);
    setErrorHosted(null);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const data = (await res.json()) as { url?: string; error?: string };
      if (data.url) {
        window.location.assign(data.url);
        return;
      }
      setErrorHosted(data.error || "No se pudo crear la sesión de pago.");
      setRedirigiendo(false);
    } catch {
      setErrorHosted("Error de conexión. Intenta de nuevo.");
      setRedirigiendo(false);
    }
  }, [plan]);

  return (
    <main className="min-h-screen bg-[color:var(--bg)] text-[color:var(--ink)]">
      {/* Barra mínima: volver + wordmark */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Link
          href="/#pricing"
          className="inline-flex items-center gap-2 text-sm text-[color:var(--muted)] transition-colors hover:text-[color:var(--ink)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Volver
        </Link>
        <Link href="/" className="text-xl font-semibold tracking-tight">
          Dona.
        </Link>
      </header>

      <div className="mx-auto max-w-6xl px-6 pb-20">
        <h1 className="mb-10 text-3xl font-semibold tracking-tight sm:text-4xl">
          Configura tu plan
        </h1>

        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_400px]">
          {/* ── Columna izquierda · detalles + pago ── */}
          <div className="min-w-0">
            <h2 className="eyebrow mb-4">Detalles del plan</h2>
            <div
              className="grid gap-3 sm:grid-cols-2"
              role="radiogroup"
              aria-label="Plan de suscripción"
            >
              {PLANES_DISPLAY.map((p) => {
                const activo = p.plan === plan;
                return (
                  <button
                    key={p.plan}
                    type="button"
                    role="radio"
                    aria-checked={activo}
                    onClick={() => setPlan(p.plan)}
                    className={`rounded-2xl border p-5 text-left transition-colors ${
                      activo
                        ? "border-[color:var(--brand)] bg-[color:var(--surface)] shadow-[0_1px_2px_rgba(11,11,18,0.04),0_10px_28px_-22px_rgba(11,11,18,0.25)]"
                        : "border-[color:var(--line)] bg-[color:var(--surface)]/60 hover:border-[color:var(--ink-2)]/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{p.nombre}</span>
                      {p.destacado && (
                        <span className="rounded-full bg-[color:var(--fill)] px-2.5 py-0.5 text-[11px] font-medium text-[color:var(--brand)]">
                          Recomendado
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-[color:var(--muted)]">
                      <span className="text-lg font-semibold text-[color:var(--ink)]">
                        {p.precio}
                      </span>{" "}
                      US{p.periodo.replace("/", " / ")}
                    </p>
                  </button>
                );
              })}
            </div>

            {/* ── Pago ── */}
            <h2 className="eyebrow mb-4 mt-10">Pago</h2>
            {PK ? (
              <div className="rounded-3xl border border-[color:var(--line)] bg-[color:var(--surface)] p-2 sm:p-4">
                {montando && (
                  <div
                    className="flex min-h-[320px] items-center justify-center gap-2 text-sm text-[color:var(--muted)]"
                    role="status"
                  >
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Preparando el pago seguro…
                  </div>
                )}
                {errorPago && !montando && (
                  <div className="flex min-h-[220px] flex-col items-center justify-center gap-4 p-6 text-center">
                    <p className="max-w-sm text-sm text-[color:var(--muted)]">
                      No pudimos cargar el formulario de pago aquí. Puedes
                      continuar en la página segura de Stripe.
                    </p>
                    <button
                      type="button"
                      onClick={() => void irAPagoHospedado()}
                      disabled={redirigiendo}
                      className="btn-primary inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium disabled:opacity-50"
                    >
                      {redirigiendo ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Lock className="h-4 w-4" />
                      )}
                      Continuar al pago seguro
                    </button>
                    {errorHosted && (
                      <p className="text-xs text-[color:var(--dato-neg)]">
                        {errorHosted}
                      </p>
                    )}
                  </div>
                )}
                {/* Contenedor del Embedded Checkout de Stripe */}
                <div
                  ref={mountRef}
                  data-testid="stripe-embedded"
                  className={montando || errorPago ? "hidden" : undefined}
                />
              </div>
            ) : (
              // Fallback sin publishable key: mismo flujo hospedado de siempre.
              <div className="flex flex-col items-start gap-4 rounded-3xl border border-[color:var(--line)] bg-[color:var(--surface)] p-6">
                <p className="text-sm text-[color:var(--muted)]">
                  Te llevaremos a la página segura de Stripe para completar el
                  pago.
                </p>
                <button
                  type="button"
                  onClick={() => void irAPagoHospedado()}
                  disabled={redirigiendo}
                  className="btn-primary inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium disabled:opacity-50"
                >
                  {redirigiendo ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Lock className="h-4 w-4" />
                  )}
                  Continuar al pago seguro
                </button>
                {errorHosted && (
                  <p className="text-xs text-[color:var(--dato-neg)]">
                    {errorHosted}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* ── Columna derecha · resumen sticky ── */}
          <aside className="lg:sticky lg:top-8 lg:self-start">
            <div className="rounded-3xl border border-[color:var(--line)] bg-[color:var(--surface)] p-7 shadow-[0_1px_2px_rgba(11,11,18,0.04),0_18px_44px_-30px_rgba(11,11,18,0.35)]">
              <h2 className="text-2xl font-semibold tracking-tight">
                Plan {planInfo.nombre}
              </h2>
              <p className="eyebrow mt-5 mb-3">Funciones destacadas</p>
              <ul className="space-y-2.5">
                {planInfo.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-sm">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--brand)]" />
                    <span className="text-[color:var(--ink-2)]">{f}</span>
                  </li>
                ))}
              </ul>

              <div className="my-6 border-t border-[color:var(--line)]" />

              <dl className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="text-[color:var(--muted)]">
                    Suscripción mensual
                  </dt>
                  <dd className="font-medium">
                    {planInfo.precio}
                    <span className="text-[color:var(--muted)]">/mes</span>
                  </dd>
                </div>
                <div className="flex items-center justify-between text-base">
                  <dt className="font-semibold">Total hoy</dt>
                  <dd className="font-semibold">{planInfo.precio} USD</dd>
                </div>
              </dl>

              <p className="mt-5 text-xs leading-relaxed text-[color:var(--muted)]">
                Sin permanencia — cancela cuando quieras. El total final (con
                impuestos, si aplican) se muestra en el formulario de pago. Pago
                procesado de forma segura por Stripe.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
