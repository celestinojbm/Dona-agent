/** @vitest-environment jsdom */
// landing/app/page.test.tsx — Páginas públicas en pausa.
//
// Inicio, checkout, success, cancel, login, dashboard y soporte muestran el
// estado real; ninguna afirma pagos, ofrece planes, pide credenciales ni
// publica un contacto aún no verificado. Rutas internas retiradas → 404.

import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";

const { authSpy, notFoundSpy } = vi.hoisted(() => ({
  authSpy: vi.fn(),
  notFoundSpy: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));
vi.mock("@/auth", () => ({ auth: authSpy }));
vi.mock("next/navigation", () => ({ notFound: notFoundSpy, redirect: vi.fn() }));

import Home from "./page";
import CheckoutPage from "./checkout/page";
import SuccessPage from "./success/page";
import CancelPage from "./cancel/page";
import LoginPage from "./login/page";
import DashboardPage from "./dashboard/page";
import SoportePage from "./soporte/page";
import EngineeringPage from "./engineering/page";
import PrototipoHero from "./prototipo/page";
import TerminosPage from "./terminos-y-condiciones/page";
import PrivacidadPage from "./politica-de-privacidad/page";

const AVISO = "Dona está completo. Todas las plazas están ocupadas y por ahora no aceptamos nuevas suscripciones ni compras.";

afterEach(() => cleanup());

const paginas: [string, () => ReactElement][] = [
  ["/", Home],
  ["/checkout", CheckoutPage],
  ["/success", SuccessPage],
  ["/cancel", CancelPage],
  ["/login", LoginPage],
  ["/dashboard", DashboardPage],
  ["/soporte", SoportePage],
];

describe.each(paginas)("página %s en pausa", (_ruta, Pagina) => {
  it("muestra el aviso de pausa y enlaces a términos y privacidad", () => {
    render(Pagina());
    expect(screen.getByRole("heading", { name: "Dona está completo" })).toBeInTheDocument();
    expect(screen.getByText(AVISO)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Términos y condiciones" })).toHaveAttribute(
      "href",
      "/terminos-y-condiciones",
    );
    expect(screen.getByRole("link", { name: "Política de privacidad" })).toHaveAttribute(
      "href",
      "/politica-de-privacidad",
    );
  });

  it("no vende, no pide credenciales ni publica contacto sin verificar", () => {
    const { container } = render(Pagina());
    const esInicio = _ruta === "/";
    const texto = container.textContent ?? "";
    expect(texto).not.toMatch(/Pago exitoso|está activa|Empezar|Ver planes|\$20|\$40/);
    expect(texto).not.toContain("WhatsApp");
    // Solo el inicio lleva formulario: la lista de espera (correo y teléfono).
    const forms = container.querySelectorAll("form");
    if (esInicio) {
      expect(forms).toHaveLength(1);
      expect(forms[0]).toHaveAttribute("aria-label", "Lista de espera");
    } else {
      expect(forms).toHaveLength(0);
    }
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull();
    expect(container.querySelector('a[href*="/dashboard"]')).toBeNull();
  });
});

describe("páginas con lógica específica", () => {
  it("success no afirma que se haya realizado un pago", () => {
    render(SuccessPage());
    expect(
      screen.getByText("Esta página no confirma pagos ni activa suscripciones."),
    ).toBeInTheDocument();
  });

  it("dashboard no lee la sesión: una sesión anterior no da acceso", () => {
    authSpy.mockResolvedValue({ user: { email: "usuario@example.com" } });
    render(DashboardPage());
    expect(authSpy).not.toHaveBeenCalled();
    expect(screen.getByText(AVISO)).toBeInTheDocument();
  });

  it("engineering y prototipo responden 404", () => {
    expect(() => EngineeringPage()).toThrow("NEXT_NOT_FOUND");
    expect(() => PrototipoHero()).toThrow("NEXT_NOT_FOUND");
    expect(notFoundSpy).toHaveBeenCalledTimes(2);
  });
});

describe("documentos legales siguen publicados con el aviso", () => {
  it.each([
    ["términos", TerminosPage],
    ["privacidad", PrivacidadPage],
  ])("%s", (_nombre, Pagina) => {
    render(Pagina());
    expect(screen.getByRole("status")).toHaveTextContent(AVISO);
    // Sin fecha de pausa inventada en el aviso.
    expect(screen.getByRole("status").textContent).not.toMatch(/\d{4}/);
  });
});
