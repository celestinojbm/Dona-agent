// landing/lib/auth-preview.test.ts — authorize y el bypass de preview.
//
// Sin VERCEL_ENV=preview la contraseña del dueño no abre sesión y un
// password "dona-" + hex sigue el flujo de Stripe, aunque las variables
// de preview estén definidas.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { crearHashPreview } from "./preview-login";

type Authorize = (c: Record<string, unknown>) => Promise<Record<string, unknown> | null>;
type JwtCb = (arg: { token: Record<string, unknown>; user?: Record<string, unknown> }) => Promise<Record<string, unknown>>;
type SessionCb = (arg: { session: Record<string, unknown>; token: Record<string, unknown> }) => Promise<Record<string, unknown>>;

let authorize: Authorize | undefined;
let jwt: JwtCb | undefined;
let sessionCb: SessionCb | undefined;

vi.mock("next-auth", () => ({
  default: (config: {
    providers: { authorize: Authorize }[];
    callbacks: { jwt: JwtCb; session: SessionCb };
  }) => {
    authorize = config.providers[0].authorize;
    jwt = config.callbacks.jwt;
    sessionCb = config.callbacks.session;
    return { handlers: {}, auth: vi.fn(), signIn: vi.fn(), signOut: vi.fn() };
  },
}));
vi.mock("next-auth/providers/credentials", () => ({
  default: (opts: unknown) => opts,
}));

const getStripe = vi.fn();
const checkLoginLockout = vi.fn();
const recordLoginAttempt = vi.fn();
const encontrarCustomerConSub = vi.fn();
vi.mock("@/lib/stripe", () => ({ getStripe }));
vi.mock("@/lib/auth-lockout-bridge", () => ({ checkLoginLockout, recordLoginAttempt }));
vi.mock("@/lib/auth-matcher", () => ({ encontrarCustomerConSub }));

const EMAIL = "dueno@example.com";
const PASSWORD = "clave-preview-7f3a9c";
// Formato "dona-" + 12 hex, armado en ejecución para no dejar un literal
// que el escáner de secretos confunda con una clave.
const PASSWORD_DONA = `dona-${"0".repeat(12)}`;
const ID_CLIENTE = ["cus", "fixture", "login"].join("_");
const ID_SUB = ["sub", "fixture", "login"].join("_");
const ID_PRECIO = ["price", "fixture"].join("_");
let hash = "";

function armarPreview(env: string) {
  vi.stubEnv("VERCEL_ENV", env);
  vi.stubEnv("PREVIEW_LOGIN_EMAIL", EMAIL);
  vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", hash);
}

function armarStripe() {
  checkLoginLockout.mockResolvedValue({ bloqueado: false, retry_after_segundos: 0 });
  recordLoginAttempt.mockResolvedValue(undefined);
  encontrarCustomerConSub.mockResolvedValue({
    customer: { id: ID_CLIENTE, email: "cliente@example.com", name: "Cliente" },
    subscription: {
      id: ID_SUB,
      items: { data: [{ price: { id: ID_PRECIO } }] },
    },
    recovery: false,
    passwordOwnerCustomerId: ID_CLIENTE,
  });
  getStripe.mockReturnValue({ customers: {}, subscriptions: {} });
}

beforeEach(async () => {
  vi.unstubAllEnvs();
  vi.stubEnv("VERCEL_ENV", "");
  vi.stubEnv("PREVIEW_LOGIN_EMAIL", "");
  vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", "");
  getStripe.mockReset();
  checkLoginLockout.mockReset();
  recordLoginAttempt.mockReset();
  encontrarCustomerConSub.mockReset();
  if (!hash) hash = crearHashPreview(PASSWORD);
  await import("@/auth");
});

describe("authorize · bypass de preview", () => {
  it.each(["production", "development", ""])(
    "VERCEL_ENV=%j no acepta la contraseña del dueño ni consulta Stripe",
    async (env) => {
      armarPreview(env);
      const res = await authorize!({ email: EMAIL, password: PASSWORD });
      expect(res).toBeNull();
      expect(getStripe).not.toHaveBeenCalled();
      expect(checkLoginLockout).not.toHaveBeenCalled();
      expect(recordLoginAttempt).not.toHaveBeenCalled();
      expect(encontrarCustomerConSub).not.toHaveBeenCalled();
    },
  );

  it("en producción un password dona- sigue el flujo de Stripe aunque existan las variables", async () => {
    armarPreview("production");
    armarStripe();
    const res = await authorize!({ email: "cliente@example.com", password: PASSWORD_DONA });
    expect(getStripe).toHaveBeenCalledTimes(1);
    expect(checkLoginLockout).toHaveBeenCalledWith("cliente@example.com");
    expect(encontrarCustomerConSub).toHaveBeenCalledTimes(1);
    expect(recordLoginAttempt).toHaveBeenCalledWith("cliente@example.com", true);
    expect(res).toMatchObject({
      id: ID_CLIENTE,
      stripeCustomerId: ID_CLIENTE,
      subscriptionId: ID_SUB,
      plan: ID_PRECIO,
    });
    expect(res).not.toHaveProperty("preview");
  });

  it("en preview abre sesión mínima y no toca Stripe ni el lockout", async () => {
    armarPreview("preview");
    armarStripe();
    checkLoginLockout.mockResolvedValue({ bloqueado: true, retry_after_segundos: 60 });
    const res = await authorize!({ email: "Dueno@Example.com", password: PASSWORD });
    expect(res).toEqual({
      id: "preview-owner",
      email: EMAIL,
      name: EMAIL,
      plan: "preview",
      preview: true,
    });
    expect(getStripe).not.toHaveBeenCalled();
    expect(checkLoginLockout).not.toHaveBeenCalled();
    expect(recordLoginAttempt).not.toHaveBeenCalled();
    expect(encontrarCustomerConSub).not.toHaveBeenCalled();
  });

  it("en preview una contraseña distinta no abre el bypass y el dona- sigue a Stripe", async () => {
    armarPreview("preview");
    armarStripe();
    expect(await authorize!({ email: EMAIL, password: "no-es-la-clave" })).toBeNull();
    expect(getStripe).not.toHaveBeenCalled();

    const res = await authorize!({ email: "cliente@example.com", password: PASSWORD_DONA });
    expect(res).toMatchObject({ subscriptionId: ID_SUB });
    expect(getStripe).toHaveBeenCalledTimes(1);
  });
});

describe("callbacks de sesión", () => {
  it("un login de Stripe no marca preview", async () => {
    const token = await jwt!({
      token: {},
      user: {
        id: ID_CLIENTE,
        email: "cliente@example.com",
        stripeCustomerId: ID_CLIENTE,
        subscriptionId: ID_SUB,
        plan: ID_PRECIO,
      },
    });
    expect(token).toEqual({
      stripeCustomerId: ID_CLIENTE,
      subscriptionId: ID_SUB,
      plan: ID_PRECIO,
    });
    const session = await sessionCb!({ session: { user: { email: "cliente@example.com" } }, token });
    expect(session).not.toHaveProperty("preview");
    expect(session).toMatchObject({
      stripeCustomerId: ID_CLIENTE,
      subscriptionId: ID_SUB,
      plan: ID_PRECIO,
    });
  });

  it("la sesión de preview no copia ids de Stripe", async () => {
    const token = await jwt!({
      token: {},
      user: {
        id: "preview-owner",
        email: EMAIL,
        name: EMAIL,
        plan: "preview",
        preview: true,
      },
    });
    expect(token.preview).toBe(true);
    expect(token.stripeCustomerId).toBeUndefined();
    expect(token.subscriptionId).toBeUndefined();
    const session = await sessionCb!({ session: { user: { email: EMAIL } }, token });
    expect(session.preview).toBe(true);
    expect(session.plan).toBe("preview");
    expect(session.stripeCustomerId).toBeUndefined();
    expect(session.subscriptionId).toBeUndefined();
  });
});
