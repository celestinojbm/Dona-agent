import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { getStripe } from "@/lib/stripe";

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

        // Search for a Stripe customer with this email that has an active subscription
        const customers = await getStripe().customers.list({
          email,
          limit: 1,
        });

        if (customers.data.length === 0) return null;

        const customer = customers.data[0];

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
