/** @vitest-environment jsdom */
// landing/app/home-redirect.test.tsx — / fuera de pausa.
//
// En esta rama DONA_EN_PAUSA es false: la home manda a /login. Con la
// pausa forzada a true, app/page.test.tsx sigue esperando la página de pausa.

import { describe, expect, it, vi } from "vitest";

const redirectSpy = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    redirectSpy(url);
    throw new Error("NEXT_REDIRECT");
  },
  notFound: vi.fn(),
}));

import Home from "./page";
import { DONA_EN_PAUSA } from "@/lib/pausa";

describe("inicio con la pausa apagada", () => {
  it("redirige a /login", () => {
    expect(DONA_EN_PAUSA).toBe(false);
    expect(() => Home()).toThrow("NEXT_REDIRECT");
    expect(redirectSpy).toHaveBeenCalledTimes(1);
    expect(redirectSpy).toHaveBeenCalledWith("/login");
  });
});
