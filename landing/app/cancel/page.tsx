"use client";

import { X, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function CancelPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6 relative z-[2]">
      <div className="glass-card rounded-2xl p-12 max-w-md w-full text-center">
        <div className="w-16 h-16 rounded-full bg-white/[0.06] flex items-center justify-center mx-auto mb-6">
          <X className="w-8 h-8 text-white/40" />
        </div>
        <h1 className="text-3xl font-normal text-white mb-4 tracking-tight">
          Pago cancelado
        </h1>
        <p className="text-white/35 font-light mb-8 leading-relaxed">
          Tu pago no fue procesado. No se realizo ningun cargo. Puedes intentar
          de nuevo cuando quieras.
        </p>
        <Link
          href="/#pricing"
          className="btn-primary inline-flex items-center gap-2 px-8 py-4 rounded-full text-sm"
        >
          Ver planes
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
