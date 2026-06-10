"use client";

// landing/app/engineering/login-form.tsx
// Form mínimo de acceso al panel: pide el token del dueño, lo POSTea a
// /api/engineering/login (que setea la cookie httpOnly) y refresca.

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginForm() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    if (!token.trim() || enviando) return;
    setEnviando(true);
    setError(null);
    try {
      const res = await fetch("/api/engineering/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim() }),
      });
      if (res.ok) {
        router.refresh();
        return;
      }
      setError("Token inválido.");
    } catch {
      setError("No se pudo validar el token. Intenta de nuevo.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-6">
      <form
        onSubmit={entrar}
        className="glass-card rounded-2xl p-10 w-full max-w-sm"
      >
        <p className="font-mono text-xs tracking-[0.3em] text-white/40 uppercase mb-2">
          Dona · Engineering
        </p>
        <h1 className="text-2xl font-light tracking-wide uppercase mb-8">
          Panel de ingeniería
        </h1>
        <label className="block text-sm text-white/50 mb-2" htmlFor="token">
          Token de acceso
        </label>
        <input
          id="token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 font-mono text-sm focus:outline-none focus:border-white/30 transition-colors"
          placeholder="••••••••••••"
        />
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={enviando || !token.trim()}
          className="btn-primary w-full mt-6 rounded-lg px-4 py-3 text-sm tracking-widest uppercase disabled:opacity-40"
        >
          {enviando ? "Validando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
