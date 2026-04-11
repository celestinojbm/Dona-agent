"use client";

import { CheckCircle2, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function SuccessPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6 relative z-[2]">
      <div className="glass-card rounded-2xl p-12 max-w-md w-full text-center">
        <CheckCircle2 className="w-16 h-16 text-white/60 mx-auto mb-6" />
        <h1 className="text-3xl font-normal text-white mb-4 tracking-tight">
          Pago exitoso
        </h1>
        <p className="text-white/35 font-light mb-8 leading-relaxed">
          Tu suscripcion a Dona esta activa. Recibiras un mensaje de bienvenida
          por WhatsApp en los proximos minutos.
        </p>
        <Link
          href="/dashboard"
          className="btn-primary inline-flex items-center gap-2 px-8 py-4 rounded-full text-sm"
        >
          Ir al dashboard
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
