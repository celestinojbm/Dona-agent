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
        "No pudimos validar tu acceso. Si ya pagaste y crees que es un error, escribenos a hola@usadona.com y lo resolvemos enseguida."
      );
    } else if (result?.ok) {
      window.location.href = "/dashboard";
    }
  }

  return (
    <div className="min-h-screen bg-[color:var(--bg)] text-[color:var(--ink)] flex items-center justify-center px-6 relative z-[2]">
      <div className="surface-static p-12 max-w-sm w-full">
        <Link
          href="/"
          className="text-2xl font-semibold tracking-tight text-[color:var(--ink)] block text-center mb-8"
        >
          Dona
        </Link>

        <h1 className="text-xl font-semibold text-[color:var(--ink)] text-center mb-2 tracking-tight">
          Inicia sesion
        </h1>
        <p className="text-sm text-[color:var(--muted)] text-center mb-8">
          Accede a tu dashboard de Dona
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="tu@correo.com"
            required
            className="w-full px-5 py-3.5 rounded-xl bg-white border border-[color:var(--line)] text-sm text-[color:var(--ink)] placeholder:text-[color:var(--muted)] focus:outline-none focus:border-[color:var(--brand)] transition-colors"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Contrasena"
            required
            className="w-full px-5 py-3.5 rounded-xl bg-white border border-[color:var(--line)] text-sm text-[color:var(--ink)] placeholder:text-[color:var(--muted)] focus:outline-none focus:border-[color:var(--brand)] transition-colors"
          />

          {error && (
            <div className="rounded-xl px-4 py-3 bg-[#e64263]/10 border border-[#e64263]/40">
              <p className="text-sm text-[color:var(--ink)]">{error}</p>
              <a
                href="mailto:hola@usadona.com"
                className="text-sm text-[color:var(--ink-2)] hover:text-[color:var(--ink)] underline mt-1 inline-block"
              >
                Escribir a soporte
              </a>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3.5 rounded-full text-sm flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? "Verificando..." : "Entrar"}
            {!loading && <ArrowRight className="w-4 h-4" />}
          </button>
        </form>

        <p className="text-xs text-[color:var(--muted)] text-center mt-6">
          Solo usuarios con suscripcion activa pueden acceder.
        </p>
      </div>
    </div>
  );
}
