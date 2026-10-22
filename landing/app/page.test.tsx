/** @vitest-environment jsdom */
// landing/app/page.test.tsx — Páginas públicas en pausa.
//
// La home es la landing v2 (CTA de acceso sin backend). Checkout, success,
// cancel, login, dashboard y soporte siguen en pausa. Rutas internas → 404.

import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

const AVISO = "Dona está en pausa. No aceptamos nuevas suscripciones ni compras.";

class ObservadorVacio {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

function instalarDom() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
  vi.stubGlobal("IntersectionObserver", ObservadorVacio);
  vi.stubGlobal("ResizeObserver", ObservadorVacio);
}

instalarDom();

afterEach(() => cleanup());

const paginas: [string, () => ReactElement][] = [
  ["/checkout", CheckoutPage],
  ["/success", SuccessPage],
  ["/cancel", CancelPage],
  ["/login", LoginPage],
  ["/dashboard", DashboardPage],
  ["/soporte", SoportePage],
];

describe("landing v2 en /", () => {
  it("muestra el titular, la pausa y los CTA sin enviar datos", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response());
    const { container } = render(Home());

    expect(screen.getByRole("heading", { level: 1, name: /Tú decides/i })).toBeInTheDocument();
    expect(screen.getByText(/No aceptamos nuevas suscripciones ni compras/)).toBeInTheDocument();
    expect(screen.getByText(/testimonio de ejemplo, sustituir/i)).toBeInTheDocument();
    expect(screen.getByText(/Precios ilustrativos/i)).toBeInTheDocument();
    expect(container.querySelector('[data-placeholder="testimonio"]')).not.toBeNull();
    expect(container.querySelector('[data-placeholder="precios"]')).not.toBeNull();

    const ctas = screen.getAllByRole("link", { name: /Pedir acceso/i });
    expect(ctas.length).toBeGreaterThan(1);
    for (const cta of ctas) {
      expect(cta.getAttribute("href") ?? "").toMatch(/^#/);
    }

    const hrefs = [...container.querySelectorAll("a")].map((nodo) => nodo.getAttribute("href") ?? "");
    expect(hrefs.some((href) => /checkout|dashboard|stripe|mailto:|\/api\//i.test(href))).toBe(false);
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(container.textContent ?? "").not.toMatch(/\$20|\$40|Ver planes|Pago exitoso|Fundadores/);

    expect(screen.getByRole("link", { name: "Términos" })).toHaveAttribute("href", "/terminos-y-condiciones");
    expect(screen.getByRole("link", { name: "Privacidad" })).toHaveAttribute(
      "href",
      "/politica-de-privacidad",
    );
    expect(screen.getByRole("link", { name: "Entrar" })).toHaveAttribute("href", "/login");

    fireEvent.click(ctas[0]);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("abre la pregunta del crédito y el menú con teclado accesible", () => {
    render(Home());
    const credito = screen.getByRole("button", { name: "¿Qué es un crédito?" });
    expect(credito).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(credito);
    expect(credito).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/unidad entera y prepaga/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    expect(screen.getByRole("button", { name: "Cerrar menú" })).toHaveAttribute("aria-expanded", "true");
  });

  it("reserva el fucsia para el punto del logo", () => {
    const { container } = render(Home());
    const html = container.innerHTML.replace(/fill="#E64263"/g, "");
    expect(container.innerHTML).toMatch(/fill="#E64263"/);
    expect(html).not.toMatch(/E64263/i);
  });
});

describe.each(paginas)("página %s en pausa", (_ruta, Pagina) => {
  it("muestra el aviso de pausa y enlaces a términos y privacidad", () => {
    render(Pagina());
    expect(screen.getByRole("heading", { name: "Dona está en pausa" })).toBeInTheDocument();
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
    const texto = container.textContent ?? "";
    expect(texto).not.toMatch(/Pago exitoso|está activa|Empezar|Ver planes|\$20|\$40/);
    expect(texto).not.toContain("WhatsApp");
    expect(container.querySelector("form")).toBeNull();
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
