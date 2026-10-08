import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { getStripe } from "@/lib/stripe";
import {
  deriveDashboardPassword,
  constantTimeEqual,
  tienePasswordFormatoValido,
} from "@/lib/dashboard-auth";
import { encontrarCustomerConSub } from "@/lib/auth-matcher";
import {
  checkLoginLockout,
  recordLoginAttempt,
} from "@/lib/auth-lockout-bridge";
import { DONA_EN_PAUSA } from "@/lib/pausa";
import { appPilotoHabilitado } from "@/lib/app-piloto";
import { llamarApp } from "@/lib/app-bridge";
import type { Workspace } from "@/lib/app-types";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        // Pausa: ningún login prospera y no se consulta Stripe, el lockout
        // del backend ni nada externo. Las sesiones anteriores (JWT) no dan
        // acceso operativo: /dashboard y las rutas /api/* privadas cortan
        // antes de leer la sesión.
        if (DONA_EN_PAUSA) return null;

        const email = credentials?.email as string | undefined;
        const password = credentials?.password as string | undefined;

        if (!email || !password) return null;

        // Gate de formato: un password que no matchea el formato derivado
        // ("dona-" + 12 hex) no puede ser válido. Rechazar acá evita pegarle a
        // Stripe y no cuenta como intento de brute-force.
        if (!tienePasswordFormatoValido(password)) return null;

        // Lockout persistente anti brute-force · consultado ANTES de Stripe.
        // Fail-open: si el backend no responde, checkLoginLockout devuelve
        // no-bloqueado (no encerramos al usuario por un hiccup del backend).
        const lockout = await checkLoginLockout(email);
        if (lockout.bloqueado) {
          console.warn(
            `[AUTH] login bloqueado por lockout · retry_after=${lockout.retry_after_segundos}s`,
          );
          return null;
        }

        // Itera TODOS los customers con ese email · admite subs en
        // active/trialing/past_due · si el password coincide con un
        // customer del email pero la sub está en otro (caso recovery
        // cross-customer), también autoriza. Lógica completa y
        // testeable en lib/auth-matcher.ts.
        const stripe = getStripe();
        const match = await encontrarCustomerConSub(email, password, {
          customers: stripe.customers,
          subscriptions: stripe.subscriptions,
          derivePassword: deriveDashboardPassword,
          passwordMatch: constantTimeEqual,
        });

        if (!match) {
          // Intento fallido (con formato válido) → cuenta para el lockout.
          await recordLoginAttempt(email, false);
          return null;
        }

        // Éxito → resetea el contador de lockout del email.
        await recordLoginAttempt(email, true);

        // Log estructurado sin PII para correlacionar el patrón de
        // recovery en producción. NO logueamos email ni password.
        if (match.recovery) {
          const shortSub = match.subscription.id.slice(0, 8) + "...";
          const shortCus = match.customer.id.slice(0, 8) + "...";
          const shortPwd = match.passwordOwnerCustomerId.slice(0, 8) + "...";
          console.warn(
            `[AUTH] recovery cross-customer · sub=${shortSub} ` +
              `dashboard_customer=${shortCus} password_customer=${shortPwd}`,
          );
        }

        return {
          id: match.customer.id,
          email: match.customer.email ?? email,
          name: match.customer.name ?? email,
          stripeCustomerId: match.customer.id,
          subscriptionId: match.subscription.id,
          plan: match.subscription.items.data[0]?.price?.id ?? "unknown",
        };
      },
    }),
    // J7.5 · Cuentas del piloto app-first (/app). Independiente de la pausa
    // y de Stripe: valida contra /internal/app/auth.verificar (scrypt +
    // lockout en el backend). Apagado si el piloto no está habilitado.
    Credentials({
      id: "cuenta",
      name: "Cuenta Dona",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!appPilotoHabilitado()) return null;
        const email = credentials?.email;
        const password = credentials?.password;
        if (typeof email !== "string" || typeof password !== "string") return null;
        if (!email.trim() || !password) return null;

        const res = await llamarApp<{ usuario_id: number; workspaces: Workspace[] }>(
          "auth.verificar",
          { email, password },
        );
        if (!res.ok) return null;
        const workspace = res.data.workspaces[0];
        if (!workspace) return null;
        return {
          id: `cuenta:${res.data.usuario_id}`,
          email: email.trim().toLowerCase(),
          tipo: "cuenta",
          usuarioId: res.data.usuario_id,
          workspaceId: workspace.id,
        };
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.stripeCustomerId = (user as { stripeCustomerId?: string })
          .stripeCustomerId;
        token.subscriptionId = (user as { subscriptionId?: string })
          .subscriptionId;
        token.plan = (user as { plan?: string }).plan;
        const cuenta = user as { tipo?: string; usuarioId?: number; workspaceId?: number };
        if (cuenta.tipo === "cuenta") {
          token.tipo = "cuenta";
          token.usuarioId = cuenta.usuarioId;
          token.workspaceId = cuenta.workspaceId;
        }
      }
      return token;
    },
    async session({ session, token }) {
      const s = session as {
        stripeCustomerId?: unknown;
        subscriptionId?: unknown;
        plan?: unknown;
        tipo?: unknown;
        usuarioId?: unknown;
        workspaceId?: unknown;
      };
      s.stripeCustomerId = token.stripeCustomerId;
      s.subscriptionId = token.subscriptionId;
      s.plan = token.plan;
      if (token.tipo === "cuenta") {
        s.tipo = "cuenta";
        s.usuarioId = token.usuarioId;
        s.workspaceId = token.workspaceId;
      }
      return session;
    },
  },
  session: { strategy: "jwt" },
});
