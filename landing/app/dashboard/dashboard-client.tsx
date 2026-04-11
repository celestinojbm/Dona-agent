"use client";

import { useState } from "react";
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
} from "lucide-react";
import Link from "next/link";

interface DashboardProps {
  session: any;
}

export default function DashboardClient({ session }: DashboardProps) {
  const [canceling, setCanceling] = useState(false);
  const [cancelDone, setCancelDone] = useState(false);

  async function handleCancel() {
    if (!confirm("Estas seguro de que quieres cancelar tu suscripcion?"))
      return;

    setCanceling(true);
    try {
      const res = await fetch("/api/cancel-subscription", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setCancelDone(true);
      } else {
        alert(data.error || "Error al cancelar. Intenta de nuevo.");
      }
    } catch {
      alert("Error de conexion. Intenta de nuevo.");
    }
    setCanceling(false);
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
        {/* Subscription */}
        <section>
          <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
            <CreditCard className="w-4 h-4" />
            Suscripcion
          </h2>

          <div className="glass-card rounded-2xl p-8">
            {cancelDone ? (
              <div className="text-center py-4">
                <XCircle className="w-10 h-10 text-white/30 mx-auto mb-3" />
                <p className="text-white/60 font-light">
                  Tu suscripcion ha sido cancelada.
                </p>
                <Link
                  href="/#pricing"
                  className="text-sm text-white/40 hover:text-white underline font-light mt-2 inline-block"
                >
                  Reactivar plan
                </Link>
              </div>
            ) : (
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-lg font-normal text-white">
                      Plan activo
                    </span>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-white/[0.06] text-white/50 font-mono">
                      {(session as any).plan === process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO
                        ? "Pro"
                        : "Premium"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-white/35 font-light">
                    <CheckCircle2 className="w-4 h-4 text-white/30" />
                    Suscripcion activa — se renueva mensualmente
                  </div>
                </div>
                <button
                  onClick={handleCancel}
                  disabled={canceling}
                  className="btn-secondary px-6 py-3 rounded-full text-sm disabled:opacity-50"
                >
                  {canceling ? "Cancelando..." : "Cancelar suscripcion"}
                </button>
              </div>
            )}
          </div>
        </section>

        {/* Connections */}
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
