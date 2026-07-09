/**
 * @vitest-environment jsdom
 */
// landing/app/checkout/checkout-client.test.tsx — "Configura tu plan"
//
// Verifica el contrato del checkout embebido SIN Stripe real:
//   - monta el Embedded Checkout pidiendo la sesión con {plan, embedded:true}
//   - cambiar de plan destruye la instancia y crea una sesión del plan nuevo
//   - ?plan=premium preselecciona el plan
//   - sin NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY cae al flujo hospedado (POST sin
//     embedded → redirect a session.url)

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// ── Mocks ──────────────────────────────────────────────────────────────────

let searchParamsMock = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsMock,
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const mountMock = vi.fn();
const destroyMock = vi.fn();
// createEmbeddedCheckoutPage es el API del Embedded Checkout en stripe-js v9.
const createEmbeddedCheckoutPage = vi.fn(
  async ({ fetchClientSecret }: { fetchClientSecret: () => Promise<string> }) => {
    await fetchClientSecret();
    return { mount: mountMock, destroy: destroyMock };
  },
);
vi.mock("@stripe/stripe-js", () => ({
  loadStripe: vi.fn(async () => ({ createEmbeddedCheckoutPage })),
}));

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  vi.resetModules();
  searchParamsMock = new URLSearchParams();
  mountMock.mockClear();
  destroyMock.mockClear();
  createEmbeddedCheckoutPage.mockClear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  process.env = { ...ORIGINAL_ENV };
});

function fetchClientSecretOk() {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ clientSecret: "cs_test_abc" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

async function renderConPk(plan?: string) {
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = "pk_test_xyz";
  if (plan) searchParamsMock = new URLSearchParams(`plan=${plan}`);
  const { default: CheckoutClient } = await import("./checkout-client");
  return render(<CheckoutClient />);
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("CheckoutClient · embebido", () => {
  it("monta el Embedded Checkout pidiendo la sesión con {plan, embedded:true}", async () => {
    const fetchSpy = fetchClientSecretOk();
    await renderConPk();

    // Pro es el plan por defecto (destacado en la landing).
    expect(screen.getByText("Plan Pro")).toBeInTheDocument();

    await waitFor(() => expect(mountMock).toHaveBeenCalled());
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/checkout");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      plan: "pro",
      embedded: true,
    });
  });

  it("?plan=premium preselecciona Premium", async () => {
    const fetchSpy = fetchClientSecretOk();
    await renderConPk("premium");
    expect(screen.getByText("Plan Premium")).toBeInTheDocument();
    await waitFor(() => expect(mountMock).toHaveBeenCalled());
    expect(
      JSON.parse((fetchSpy.mock.calls[0][1] as RequestInit).body as string).plan,
    ).toBe("premium");
  });

  it("cambiar de plan destruye la instancia y crea sesión del plan nuevo", async () => {
    const fetchSpy = fetchClientSecretOk();
    await renderConPk();
    await waitFor(() => expect(mountMock).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("radio", { name: /Premium/i }));

    await waitFor(() => expect(destroyMock).toHaveBeenCalled());
    await waitFor(() => expect(fetchSpy.mock.calls.length).toBeGreaterThan(1));
    const ultima = fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1];
    expect(JSON.parse((ultima[1] as RequestInit).body as string)).toEqual({
      plan: "premium",
      embedded: true,
    });
    // El resumen sigue al plan elegido.
    expect(screen.getByText("Plan Premium")).toBeInTheDocument();
  });

  it("si el embebido falla, ofrece continuar al pago hospedado", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: "checkout_failed" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await renderConPk();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Continuar al pago seguro/i }),
      ).toBeInTheDocument(),
    );
  });
});

describe("CheckoutClient · fallback sin publishable key", () => {
  it("sin la env muestra el botón hospedado y NO intenta el embebido", async () => {
    delete process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
    const { default: CheckoutClient } = await import("./checkout-client");
    render(<CheckoutClient />);

    expect(
      screen.getByRole("button", { name: /Continuar al pago seguro/i }),
    ).toBeInTheDocument();
    expect(createEmbeddedCheckoutPage).not.toHaveBeenCalled();
  });

  it("el botón hospedado POSTea {plan} sin embedded y redirige a session.url", async () => {
    delete process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ url: "https://stripe.test/sesion" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    // window.location.assign no es espiable directo en jsdom: se reemplaza.
    const originalLocation = window.location;
    const assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { ...originalLocation, assign: assignMock },
      writable: true,
      configurable: true,
    });
    try {
      const { default: CheckoutClient } = await import("./checkout-client");
      render(<CheckoutClient />);
      fireEvent.click(
        screen.getByRole("button", { name: /Continuar al pago seguro/i }),
      );
      await waitFor(() =>
        expect(assignMock).toHaveBeenCalledWith("https://stripe.test/sesion"),
      );
      const body = JSON.parse(
        (fetchSpy.mock.calls[0][1] as RequestInit).body as string,
      );
      expect(body).toEqual({ plan: "pro" });
    } finally {
      Object.defineProperty(window, "location", {
        value: originalLocation,
        writable: true,
        configurable: true,
      });
    }
  });
});
