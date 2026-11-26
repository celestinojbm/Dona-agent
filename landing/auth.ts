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

        // Itera TODOS los customers con ese email y admite subs en
        // active/trialing/past_due, pero solo con match exacto: la sesión es
        // la del MISMO customer cuyo password derivado coincidió y que tiene
        // la sub válida. No hay recovery cross-customer (issue #345): si el
        // password es de un customer sin sub válida, el login falla aunque
        // otro customer del mismo email tenga sub. Lógica y tests en
        // lib/auth-matcher.ts.
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
      }
      return token;
    },
    async session({ session, token }) {
      const s = session as {
        stripeCustomerId?: unknown;
        subscriptionId?: unknown;
        plan?: unknown;
      };
      s.stripeCustomerId = token.stripeCustomerId;
      s.subscriptionId = token.subscriptionId;
      s.plan = token.plan;
      return session;
    },
  },
  session: { strategy: "jwt" },
});
