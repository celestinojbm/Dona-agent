"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    setLoading(false);

    if (result?.error) {
      setError(
        "Tu suscripcion no esta activa. Selecciona un plan para continuar."
      );
    } else if (result?.ok) {
      window.location.href = "/dashboard";
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6 relative z-[2]">
      <div className="glass-card rounded-2xl p-12 max-w-sm w-full">
        <Link
          href="/"
          className="text-2xl font-normal text-white block text-center mb-8"
        >
          Dona
        </Link>

        <h1 className="text-xl font-normal text-white text-center mb-2 tracking-tight">
          Inicia sesion
        </h1>
        <p className="text-sm text-white/35 font-light text-center mb-8">
          Accede a tu dashboard de Dona
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@correo.com"
            required
            className="w-full px-5 py-3.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 transition-colors font-light"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Contrasena"
            required
            className="w-full px-5 py-3.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-white/20 transition-colors font-light"
          />

          {error && (
            <div className="glass-card rounded-xl px-4 py-3 border-red-500/20">
              <p className="text-sm text-red-400/80 font-light">{error}</p>
              <Link
                href="/#pricing"
                className="text-sm text-white/50 hover:text-white underline font-light mt-1 inline-block"
              >
                Ver planes disponibles
              </Link>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3.5 rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? "Verificando..." : "Entrar"}
            {!loading && <ArrowRight className="w-4 h-4" />}
          </button>
        </form>

        <p className="text-xs text-white/20 font-light text-center mt-6">
          Solo usuarios con suscripcion activa pueden acceder.
        </p>
      </div>
    </div>
  );
}
