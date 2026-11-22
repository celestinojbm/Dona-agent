// landing/lib/auth-pausa.test.ts — Login desactivado en pausa.
//
// Captura la config que auth.ts pasa a NextAuth y ejecuta authorize con
// credenciales de formato válido: debe devolver null sin consultar Stripe,
// el lockout del backend ni la red.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { crearHashPreview } from "./preview-login";

// Rama staging/despausa-preview: la constante real es false (preview). Este
// test verifica el comportamiento EN PAUSA, así que la fuerza a true.
vi.mock("@/lib/pausa", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/pausa")>()),
  DONA_EN_PAUSA: true,
}));

type Authorize = (c: Record<string, unknown>) => Promise<unknown>;
let authorize: Authorize | undefined;

vi.mock("next-auth", () => ({
  default: (config: { providers: { authorize: Authorize }[] }) => {
    authorize = config.providers[0].authorize;
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

const fetchSpy = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("auth.ts · authorize en pausa", () => {
  it("rechaza un login con credenciales de formato válido sin consultar nada", async () => {
    await import("@/auth");
    expect(authorize).toBeTypeOf("function");

    // Contraseña con el FORMATO válido ("dona-" + 12 hex) construida en
    // ejecución: no es un secreto y así no parece una clave literal.
    const res = await authorize!({
      email: "usuario@example.com",
      password: `dona-${"0".repeat(12)}`,
    });

    expect(res).toBeNull();
    expect(getStripe).not.toHaveBeenCalled();
    expect(checkLoginLockout).not.toHaveBeenCalled();
    expect(recordLoginAttempt).not.toHaveBeenCalled();
    expect(encontrarCustomerConSub).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("en pausa tampoco acepta el bypass de preview", async () => {
    await import("@/auth");
    const password = "clave-preview-durante-pausa";
    vi.stubEnv("VERCEL_ENV", "preview");
    vi.stubEnv("PREVIEW_LOGIN_EMAIL", "usuario@example.com");
    vi.stubEnv("PREVIEW_LOGIN_PASSWORD_HASH", crearHashPreview(password));

    const res = await authorize!({
      email: "usuario@example.com",
      password,
    });

    expect(res).toBeNull();
    expect(getStripe).not.toHaveBeenCalled();
    expect(checkLoginLockout).not.toHaveBeenCalled();
    expect(recordLoginAttempt).not.toHaveBeenCalled();
    expect(encontrarCustomerConSub).not.toHaveBeenCalled();
  });
});
