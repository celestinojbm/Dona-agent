import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { getStripe } from "@/lib/stripe";
import {
  deriveDashboardPassword,
  constantTimeEqual,
} from "@/lib/dashboard-auth";
import { encontrarCustomerConSub } from "@/lib/auth-matcher";

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

        if (!match) return null;

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
