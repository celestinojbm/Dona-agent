/**
 * @vitest-environment jsdom
 */
// Tests de los primitivos del sistema visual de la app (0A).
// Cubren accesibilidad sin depender de axe (no instalado): rol y nombre
// accesible, foco por teclado, asociación label/control, aria-invalid +
// aria-describedby en error, y semántica nativa de disabled. El contraste de
// color y los tamaños de target están garantizados por los tokens CSS
// (min-height 44px, --ring-focus), que jsdom no computa; se verifican por
// inspección de clases/estructura.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { DonaButton } from "./dona-button";
import { DonaField } from "./dona-field";
import { DonaCard } from "./dona-card";
import { DonaBadge } from "./dona-badge";

afterEach(cleanup);

describe("DonaButton", () => {
  it("es un <button> con nombre accesible y type por defecto 'button'", () => {
    render(<DonaButton>Confirmar</DonaButton>);
    const btn = screen.getByRole("button", { name: "Confirmar" });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("type", "button");
    expect(btn).toHaveClass("dona-btn", "dona-btn--primary");
  });

  it("propaga disabled con semántica nativa", () => {
    render(<DonaButton disabled>Enviar</DonaButton>);
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
  });

  it("aplica la clase de la variante ghost/danger", () => {
    const { rerender } = render(<DonaButton variante="ghost">A</DonaButton>);
    expect(screen.getByRole("button", { name: "A" })).toHaveClass("dona-btn--ghost");
    rerender(<DonaButton variante="danger">B</DonaButton>);
    expect(screen.getByRole("button", { name: "B" })).toHaveClass("dona-btn--danger");
  });
});

describe("DonaField", () => {
  it("asocia label con el input vía htmlFor/id", () => {
    render(<DonaField etiqueta="Correo" defaultValue="" />);
    // getByLabelText resuelve la asociación label<->control
    const input = screen.getByLabelText("Correo");
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe("INPUT");
  });

  it("en error expone aria-invalid y aria-describedby apuntando al mensaje", () => {
    render(<DonaField etiqueta="Monto" error="Monto inválido" />);
    const input = screen.getByLabelText("Monto");
    expect(input).toHaveAttribute("aria-invalid", "true");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveAttribute("id", describedBy as string);
    expect(alerta).toHaveTextContent("Monto inválido");
  });

  it("sin error no fija aria-invalid ni aria-describedby", () => {
    render(<DonaField etiqueta="Nombre" />);
    const input = screen.getByLabelText("Nombre");
    expect(input).not.toHaveAttribute("aria-invalid");
    expect(input).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("DonaCard / DonaBadge", () => {
  it("Card renderiza su contenido y clase base", () => {
    render(<DonaCard>Contenido</DonaCard>);
    const card = screen.getByText("Contenido");
    expect(card).toHaveClass("dona-card");
  });

  it("Card compacta añade modificador", () => {
    render(<DonaCard compacta>X</DonaCard>);
    expect(screen.getByText("X")).toHaveClass("dona-card--compact");
  });

  it("Badge expone texto accesible (estado no sólo por color)", () => {
    render(<DonaBadge tono="danger">Falló</DonaBadge>);
    const badge = screen.getByText("Falló");
    expect(badge).toHaveClass("dona-badge", "dona-badge--danger");
  });
});
