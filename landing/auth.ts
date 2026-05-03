import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { getStripe } from "@/lib/stripe";
import {
  deriveDashboardPassword,
  constantTimeEqual,
} from "@/lib/dashboard-auth";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = credentials?.email as string | undefined;
        const password = credentials?.password as string | undefined;

        if (!email || !password) return null;

        // Search for a Stripe customer with this email
        const customers = await getStripe().customers.list({
          email,
          limit: 1,
        });

        if (customers.data.length === 0) return null;

        const customer = customers.data[0];

        // T1.4.B — Validar password ANTES de revelar nada del customer.
        // password = "dona-" + hex(HMAC-SHA256(customer.id, DASHBOARD_PASSWORD_SECRET))[:12]
        // Si DASHBOARD_PASSWORD_SECRET no está configurada, derive() devuelve null
        // y rechazamos. NO hay path permisivo: mejor bloquear logins que aceptar
        // sin password.
        const expected = deriveDashboardPassword(customer.id);
        if (!expected || !constantTimeEqual(password, expected)) {
          return null;
        }

        // Check for active subscription
        const subscriptions = await getStripe().subscriptions.list({
          customer: customer.id,
          status: "active",
          limit: 1,
        });

        if (subscriptions.data.length === 0) return null;

        const sub = subscriptions.data[0];

        return {
          id: customer.id,
          email: customer.email ?? email,
          name: customer.name ?? email,
          stripeCustomerId: customer.id,
          subscriptionId: sub.id,
          plan: sub.items.data[0]?.price?.id ?? "unknown",
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
        token.stripeCustomerId = (user as any).stripeCustomerId;
        token.subscriptionId = (user as any).subscriptionId;
        token.plan = (user as any).plan;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).stripeCustomerId = token.stripeCustomerId;
      (session as any).subscriptionId = token.subscriptionId;
      (session as any).plan = token.plan;
      return session;
    },
  },
  session: { strategy: "jwt" },
});
