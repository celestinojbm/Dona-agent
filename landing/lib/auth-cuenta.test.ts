// landing/lib/auth-cuenta.test.ts — Provider "cuenta" del piloto app-first.
//
// Independiente de la pausa y de Stripe; apagado si el piloto no está
// habilitado. La sesión resultante lleva tipo "cuenta" + ids, nunca datos
// de Stripe.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Authorize = (c: Record<string, unknown>) => Promise<unknown>;
type Config = {
  providers: { id?: string; authorize: Authorize }[];
  callbacks: {
    jwt: (a: { token: Record<string, unknown>; user?: unknown }) => Promise<Record<string, unknown>>;
    session: (a: { session: Record<string, unknown>; token: Record<string, unknown> }) => Promise<Record<string, unknown>>;
  };
};
let config: Config | undefined;

vi.mock("next-auth", () => ({
  default: (c: Config) => {
    config = c;
    return { handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() };
  },
}));
vi.mock("next-auth/providers/credentials", () => ({ default: (opts: unknown) => opts }));

const getStripe = vi.fn();
const llamarApp = vi.fn();
vi.mock("@/lib/stripe", () => ({ getStripe }));
vi.mock("@/lib/app-bridge", () => ({ llamarApp }));

async function authorizeCuenta(): Promise<Authorize> {
  await import("@/auth");
  const provider = config!.providers.find((p) => p.id === "cuenta");
  expect(provider).toBeDefined();
  return provider!.authorize;
}

beforeEach(() => {
  llamarApp.mockReset();
  vi.stubEnv("DONA_APP_PILOTO_ENABLED", "true");
});
afterEach(() => vi.unstubAllEnvs());

describe("provider cuenta", () => {
  it("con el piloto apagado no consulta nada", async () => {
    vi.stubEnv("DONA_APP_PILOTO_ENABLED", "");
    const authorize = await authorizeCuenta();
    expect(await authorize({ email: "ana@example.com", password: "contraseña-larga-1" })).toBeNull();
    expect(llamarApp).not.toHaveBeenCalled();
  });

  it("valida contra el backend y emite una identidad de cuenta", async () => {
    llamarApp.mockResolvedValue({
      ok: true,
      data: { usuario_id: 3, workspaces: [{ id: 9, nombre: "Mi espacio", rol: "owner" }] },
    });
    const authorize = await authorizeCuenta();
    const user = await authorize({ email: " Ana@Example.com ", password: "contraseña-larga-1" });
    expect(llamarApp).toHaveBeenCalledWith("auth.verificar", {
      email: " Ana@Example.com ",
      password: "contraseña-larga-1",
    });
    expect(user).toEqual({
      id: "cuenta:3",
      email: "ana@example.com",
      tipo: "cuenta",
      usuarioId: 3,
      workspaceId: 9,
    });
    expect(getStripe).not.toHaveBeenCalled();
  });

  it("credenciales rechazadas, sin workspace o datos raros → null", async () => {
    const authorize = await authorizeCuenta();
    llamarApp.mockResolvedValueOnce({ ok: false, status: 401, error: "credenciales_invalidas" });
    expect(await authorize({ email: "ana@example.com", password: "x".repeat(12) })).toBeNull();
    llamarApp.mockResolvedValueOnce({ ok: true, data: { usuario_id: 3, workspaces: [] } });
    expect(await authorize({ email: "ana@example.com", password: "x".repeat(12) })).toBeNull();
    expect(await authorize({ email: ["ana@example.com"], password: "x".repeat(12) })).toBeNull();
    expect(await authorize({ email: "ana@example.com", password: "" })).toBeNull();
    expect(llamarApp).toHaveBeenCalledTimes(2);
  });

  it("jwt y session propagan tipo e ids solo para cuentas", async () => {
    await authorizeCuenta();
    const { jwt, session } = config!.callbacks;
    const token = await jwt({ token: {}, user: { tipo: "cuenta", usuarioId: 3, workspaceId: 9 } });
    expect(token).toMatchObject({ tipo: "cuenta", usuarioId: 3, workspaceId: 9 });
    expect(await session({ session: {}, token })).toMatchObject({
      tipo: "cuenta",
      usuarioId: 3,
      workspaceId: 9,
    });

    const antiguo = await jwt({ token: {}, user: { stripeCustomerId: "cus_x", subscriptionId: "sub_x" } });
    expect(antiguo.tipo).toBeUndefined();
    expect((await session({ session: {}, token: antiguo })).tipo).toBeUndefined();
  });
});
