/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-action-center-detalle.test.tsx
//
// Tests del flujo de revisión y decisión del Centro de acción:
//   - abrir el detalle de una acción y ver estado, detalle, línea de
//     tiempo y resultado legible
//   - confirmar antes de aprobar / rechazar / ejecutar (el backend solo
//     se llama al confirmar)
//   - filtrar el historial por estado
//   - confirmación dedicada HIGH desde el panel

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
  within,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionActionCenter from "./seccion-action-center";

// Radix Dialog usa APIs que jsdom no implementa · stubs mínimos.
beforeEach(() => {
  vi.stubGlobal("alert", vi.fn());
  if (!("ResizeObserver" in globalThis)) {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  }
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.scrollIntoView = () => {};
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function accionBase(overrides: Record<string, unknown> = {}) {
  return {
    id: 9,
    opportunity_id: "opp_9",
    playbook_id: "diagnostico_a_plan_semanal",
    tipo_accion: "generar_plan_semanal",
    titulo: "Plan semanal del negocio",
    descripcion: "Genera un plan semanal a partir del diagnóstico.",
    razon_recomendacion: "Tu diagnóstico está completo",
    estado: "needs_approval",
    riesgo: "medium",
    costo_creditos_estimado: 8,
    requires_approval: true,
    result_json: "{}",
    error_message: "",
    created_at: "2026-05-09T00:00:00Z",
    updated_at: "2026-05-09T01:00:00Z",
    approved_at: null,
    rejected_at: null,
    completed_at: null,
    next_required_action: "approval_required",
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetchCola(respuestas: Response[]) {
  const spy = vi.fn();
  respuestas.forEach((r) => spy.mockResolvedValueOnce(r));
  // Cualquier llamada extra devuelve la lista vacía para no romper el
  // refresco posterior a una decisión.
  spy.mockResolvedValue(jsonResponse({ acciones: [], count: 0 }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

async function abrirDetalle(titulo: RegExp | string) {
  const card = (await screen.findByText(titulo)).closest("div.surface-card");
  const boton = within(card as HTMLElement).getByRole("button", {
    name: /Ver detalle/i,
  });
  fireEvent.click(boton);
  return await screen.findByRole("dialog");
}

describe("Centro de acción · panel de detalle", () => {
  it("muestra estado, detalle, línea de tiempo y resultado legible", async () => {
    const accion = accionBase({
      estado: "completed",
      completed_at: "2026-05-10T14:00:00Z",
      result_json: JSON.stringify({ canal: "whatsapp", enviados: 3 }),
    });
    stubFetchCola([jsonResponse({ acciones: [accion], count: 1 })]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    // Estado y detalle
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /Completada/,
    );
    expect(within(dialog).getByText(/Riesgo Medio/i)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Genera un plan semanal a partir del diagnóstico/i),
    ).toBeInTheDocument();
    // Identificadores reales del payload
    expect(within(dialog).getByText("generar_plan_semanal")).toBeInTheDocument();
    expect(
      within(dialog).getByText("diagnostico_a_plan_semanal"),
    ).toBeInTheDocument();
    // Línea de tiempo con los timestamps del backend
    expect(within(dialog).getByText("Creada:")).toBeInTheDocument();
    expect(within(dialog).getByText("Completada:")).toBeInTheDocument();
    // Resultado en filas, no en JSON crudo
    expect(within(dialog).getByText("canal")).toBeInTheDocument();
    expect(within(dialog).getByText("whatsapp")).toBeInTheDocument();
    expect(within(dialog).getByText("3")).toBeInTheDocument();
    // Acción cerrada · no ofrece decisiones
    expect(
      within(dialog).getByText(/ya no admite decisiones/i),
    ).toBeInTheDocument();
  });

  it("documenta que no hay historial de eventos por acción", async () => {
    stubFetchCola([jsonResponse({ acciones: [accionBase()], count: 1 })]);
    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);
    expect(
      within(dialog).getByText(/no expone\s+un historial de eventos por acción/i),
    ).toBeInTheDocument();
  });

  it("aprobar exige confirmación y solo entonces llama al backend", async () => {
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "approved" }) }),
      jsonResponse({ acciones: [accionBase({ estado: "approved" })], count: 1 }),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    // Aparece la confirmación y todavía no se llamó al endpoint
    expect(
      within(dialog).getByText(/¿Aprobar esta acción\?/i),
    ).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalledWith(
      "/api/automation/acciones/9/aprobar",
      expect.anything(),
    );

    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        "/api/automation/acciones/9/aprobar",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("rechazar pide confirmación desde la tarjeta antes de llamar al backend", async () => {
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "rejected" }) }),
      jsonResponse({ acciones: [], count: 0 }),
    ]);

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Plan semanal del negocio/)).closest(
      "div.surface-card",
    ) as HTMLElement;

    fireEvent.click(within(card).getByRole("button", { name: /Rechazar/i }));
    expect(
      within(card).getByText(/¿Rechazar esta acción\?/i),
    ).toBeInTheDocument();
    // Cancelar no llama al backend
    fireEvent.click(within(card).getByRole("button", { name: /^Cancelar$/i }));
    expect(spy).not.toHaveBeenCalledWith(
      "/api/automation/acciones/9/rechazar",
      expect.anything(),
    );

    fireEvent.click(within(card).getByRole("button", { name: /Rechazar/i }));
    fireEvent.click(within(card).getByRole("button", { name: /Sí, rechazar/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        "/api/automation/acciones/9/rechazar",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("ejecutar dry-run confirma y anuncia el resultado por aria-live", async () => {
    const accion = accionBase({
      estado: "pending",
      riesgo: "low",
      requires_approval: false,
      next_required_action: "execute_available",
    });
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accion], count: 1 }),
      jsonResponse({ accion }),
      jsonResponse({ acciones: [accion], count: 1 }),
    ]);

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Plan semanal del negocio/)).closest(
      "div.surface-card",
    ) as HTMLElement;

    fireEvent.click(
      within(card).getByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    );
    expect(within(card).getByText(/dry-run/i)).toBeInTheDocument();

    fireEvent.click(within(card).getByRole("button", { name: /Sí, ejecutar/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        "/api/automation/acciones/9/ejecutar",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        /ejecutar registrada correctamente/i,
      ),
    );
  });
});

describe("Centro de acción · historial", () => {
  it("filtra por estado con los estados presentes en los datos", async () => {
    const completada = accionBase({
      id: 21,
      titulo: "Acción completada",
      estado: "completed",
      completed_at: "2026-05-11T10:00:00Z",
    });
    const rechazada = accionBase({
      id: 22,
      titulo: "Acción rechazada",
      estado: "rejected",
      rejected_at: "2026-05-11T11:00:00Z",
    });
    stubFetchCola([
      jsonResponse({ acciones: [completada, rechazada], count: 2 }),
    ]);

    render(<SeccionActionCenter />);
    await screen.findByText(/Historial \(2\)/i);

    fireEvent.click(screen.getByRole("button", { name: /Rechazadas/i }));
    expect(screen.getByText(/Historial \(1 de 2\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Acción rechazada/)).toBeInTheDocument();
    expect(screen.queryByText(/Acción completada/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^Todas$/i }));
    expect(screen.getByText(/Historial \(2\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Acción completada/)).toBeInTheDocument();
  });

  it("abre el detalle de una acción del historial", async () => {
    const rechazada = accionBase({
      id: 22,
      titulo: "Acción rechazada",
      estado: "rejected",
      rejected_at: "2026-05-11T11:00:00Z",
      error_message: "El usuario no quiso continuar",
    });
    stubFetchCola([jsonResponse({ acciones: [rechazada], count: 1 })]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Acción rechazada/);
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /Rechazada/,
    );
    expect(within(dialog).getByText("Rechazada:")).toBeInTheDocument();
    expect(
      within(dialog).getByText(/El usuario no quiso continuar/i),
    ).toBeInTheDocument();
  });
});

describe("Centro de acción · confirmación HIGH desde el panel", () => {
  it("pide preview y confirmación literal ENVIAR", async () => {
    const accion = accionBase({
      id: 55,
      titulo: "Enviar mensaje WhatsApp real",
      tipo_accion: "enviar_mensaje_whatsapp",
      riesgo: "high",
      estado: "approved",
      next_required_action: "dedicated_confirmation_required",
      execution_block_reason: "Requiere preview y confirmación literal.",
    });
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accion], count: 1 }),
      jsonResponse({
        ok: true,
        accion_id: 55,
        tipo_accion: "enviar_mensaje_whatsapp",
        titulo: accion.titulo,
        descripcion: accion.descripcion,
        riesgo: "high",
        estado: "approved",
        costo_creditos_estimado: 5,
        destino_short: "+5****4567",
        numero_destino: "+521****4567",
        mensaje_preview: "Hola Ana, confirmo tu pedido.",
        longitud_mensaje: 29,
        confirmacion_requerida: "ENVIAR",
      }),
      jsonResponse({
        accion: { ...accion, estado: "completed" },
        ejecucion: { estado_final: "completed" },
      }),
      jsonResponse({ acciones: [], count: 0 }),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Enviar mensaje WhatsApp real/);

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Confirmar envío HIGH/i }),
    );
    await waitFor(() =>
      expect(
        within(dialog).getByText(/Preview de envío HIGH/i),
      ).toBeInTheDocument(),
    );
    expect(within(dialog).getByText(/\+5\*\*\*\*4567/)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Hola Ana, confirmo tu pedido/i),
    ).toBeInTheDocument();

    const input = within(dialog).getByLabelText(/Escribe ENVIAR para confirmar/i);
    fireEvent.change(input, { target: { value: "enviar" } });
    expect(
      within(dialog).getByRole("button", { name: /Confirmar y enviar/i }),
    ).toBeDisabled();

    fireEvent.change(input, { target: { value: "ENVIAR" } });
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Confirmar y enviar/i }),
    );
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        "/api/automation/acciones/55/high-confirmar",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ confirmacion: "ENVIAR" }),
        }),
      ),
    );
  });
});
