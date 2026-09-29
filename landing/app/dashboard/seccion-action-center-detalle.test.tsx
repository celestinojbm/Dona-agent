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
        /Ejecución dry-run registrada/i,
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

describe("Centro de acción · estados del panel (error, éxito, vacío)", () => {
  it("muestra el error real del backend en el panel y no duplica el anuncio global", async () => {
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      // 409 real de la ruta high-confirmar/alta confirmación
      jsonResponse({ error: "high_confirmation_not_available" }, 409),
      jsonResponse({ acciones: [accionBase()], count: 1 }),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Sí, aprobar/i }),
    );

    const alerta = await within(dialog).findByRole("alert");
    expect(alerta).toHaveTextContent(/ya no admite esta confirmación/i);
    expect(spy).toHaveBeenCalledWith(
      "/api/automation/acciones/9/aprobar",
      expect.objectContaining({ method: "POST" }),
    );
    // El panel es la superficie que decide: la región global de la
    // sección queda vacía para no anunciar lo mismo dos veces.
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("muestra el éxito de la decisión en el panel", async () => {
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "approved" }) }),
      jsonResponse({
        acciones: [accionBase({ estado: "approved" })],
        count: 1,
      }),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Sí, aprobar/i }),
    );

    const exito = await within(dialog).findByRole("status");
    expect(exito).toHaveTextContent(/Acción aprobada/i);
    expect(spy).toHaveBeenCalledWith(
      "/api/automation/acciones/9/aprobar",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("mantiene el panel abierto si el refresco de la lista falla", async () => {
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "approved" }) }),
      // El refresco posterior falla: el panel conserva el último snapshot.
      jsonResponse({ error: "backend_unavailable" }, 502),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Sí, aprobar/i }),
    );

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        "/api/automation/acciones/9/aprobar",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    // El panel sigue montado con la acción aunque la lista no se pudo leer.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      within(screen.getByRole("dialog")).getByText("Plan semanal del negocio"),
    ).toBeInTheDocument();
  });

  it("POST exitoso + GET fallido: decisión registrada, estado sin verificar y sin repetir la decisión", async () => {
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "approved" }) }),
      // El GET posterior a la decisión falla.
      jsonResponse({ error: "backend_unavailable" }, 502),
      // "Actualizar estado" ya responde con el estado real.
      jsonResponse({
        acciones: [
          accionBase({
            estado: "approved",
            approved_at: "2026-05-09T02:00:00Z",
            next_required_action: "execute_available",
          }),
        ],
        count: 1,
      }),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Sí, aprobar/i }),
    );

    // Distingue "decisión registrada" de "estado actualizado".
    const aviso = await within(dialog).findByText(/Acción aprobada\./i);
    expect(aviso).toHaveAttribute("role", "status");
    expect(aviso).toHaveTextContent(/No pudimos cargar su estado actualizado/i);
    expect(aviso).not.toHaveTextContent(/ya muestra su nuevo estado/i);
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /sin verificar/i,
    );

    // El snapshot sigue diciendo "needs_approval", pero no se ofrecen
    // controles basados en él.
    expect(
      within(dialog).queryByRole("button", { name: /^Aprobar$/i }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).queryByRole("button", { name: /^Rechazar$/i }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).queryByRole("button", { name: /Ejecutar/i }),
    ).not.toBeInTheDocument();
    const llamadasAprobar = () =>
      spy.mock.calls.filter(([url]) => url === "/api/automation/acciones/9/aprobar")
        .length;
    expect(llamadasAprobar()).toBe(1);

    // Actualizar estado recarga la lista y ofrece solo lo que permite el
    // estado real.
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Actualizar estado/i }),
    );
    expect(
      await within(dialog).findByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    ).toBeInTheDocument();
    expect(
      within(dialog).queryByRole("button", { name: /^Aprobar$/i }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).queryByText(/No pudimos confirmar el estado actual/i),
    ).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/Acción aprobada\./i)).not.toBeInTheDocument();
    expect(llamadasAprobar()).toBe(1);
  });

  it("si Actualizar estado vuelve a fallar, las decisiones siguen en pausa", async () => {
    stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "rejected" }) }),
      jsonResponse({ error: "backend_unavailable" }, 502),
      jsonResponse({ error: "backend_timeout" }, 504),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Rechazar$/i }));
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Sí, rechazar/i }),
    );
    await within(dialog).findByText(/Acción rechazada\./i);

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Actualizar estado/i }),
    );
    const alerta = await within(dialog).findByRole("alert");
    expect(alerta).toHaveTextContent(/Seguimos sin poder cargar el estado/i);
    expect(
      within(dialog).queryByRole("button", { name: /^Rechazar$/i }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: /Actualizar estado/i }),
    ).toBeInTheDocument();
  });

  it("HIGH confirmada + GET fallido no afirma estado ni reofrece la confirmación", async () => {
    const accion = accionBase({
      id: 55,
      titulo: "Enviar mensaje WhatsApp real",
      riesgo: "high",
      estado: "approved",
      next_required_action: "dedicated_confirmation_required",
    });
    const spy = stubFetchCola([
      jsonResponse({ acciones: [accion], count: 1 }),
      jsonResponse({
        accion_id: 55,
        destino_short: "+5****4567",
        mensaje_preview: "Hola",
        costo_creditos_estimado: 0,
        riesgo: "high",
        confirmacion_requerida: "ENVIAR",
      }),
      jsonResponse({ accion: { ...accion, estado: "completed" } }),
      jsonResponse({ error: "backend_unavailable" }, 502),
    ]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Enviar mensaje WhatsApp real/);

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Confirmar envío HIGH/i }),
    );
    const input = await within(dialog).findByLabelText(
      /Escribe ENVIAR para confirmar/i,
    );
    fireEvent.change(input, { target: { value: "ENVIAR" } });
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Confirmar y enviar/i }),
    );

    const aviso = await within(dialog).findByText(/Confirmación HIGH registrada\./i);
    expect(aviso).toHaveTextContent(/No pudimos cargar su estado actualizado/i);
    expect(
      within(dialog).queryByRole("button", { name: /Confirmar envío HIGH/i }),
    ).not.toBeInTheDocument();
    expect(
      spy.mock.calls.filter(
        ([url]) => url === "/api/automation/acciones/55/high-confirmar",
      ).length,
    ).toBe(1);
  });

  it("POST sin respuesta: avisa que la decisión es incierta y no la reofrece", async () => {
    const spy = vi.fn();
    spy.mockResolvedValueOnce(jsonResponse({ acciones: [accionBase()], count: 1 }));
    spy.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    spy.mockResolvedValueOnce(jsonResponse({ error: "backend_unavailable" }, 502));
    vi.stubGlobal("fetch", spy);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(
      within(dialog).getByRole("button", { name: /Sí, aprobar/i }),
    );

    const alerta = await within(dialog).findByRole("alert");
    expect(alerta).toHaveTextContent(/no sabemos si se registró/i);
    expect(
      within(dialog).queryByRole("button", { name: /^Aprobar$/i }),
    ).not.toBeInTheDocument();
  });

  it("desde la tarjeta: POST exitoso + GET fallido no anuncia la lista como actualizada", async () => {
    stubFetchCola([
      jsonResponse({ acciones: [accionBase()], count: 1 }),
      jsonResponse({ accion: accionBase({ estado: "approved" }) }),
      jsonResponse({ error: "backend_unavailable" }, 502),
    ]);

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Plan semanal del negocio/)).closest(
      "div.surface-card",
    ) as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(card).getByRole("button", { name: /Sí, aprobar/i }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/Acción aprobada\./i),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      /No pudimos cargar su estado actualizado/i,
    );
    // Sin lista fresca no quedan tarjetas con controles del estado viejo.
    expect(screen.getByText(/No pudimos cargar tus acciones/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^Aprobar$/i }),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["aprobar", /^Aprobar$/i, /Sí, aprobar/i, /Acción aprobada\./i, {}],
    ["rechazar", /^Rechazar$/i, /Sí, rechazar/i, /Acción rechazada\./i, {}],
    [
      "ejecutar",
      /Ejecutar \(dry-run\)/i,
      /Sí, ejecutar/i,
      /Ejecución dry-run registrada\./i,
      { riesgo: "low", estado: "pending", next_required_action: "execute_available" },
    ],
  ] as const)(
    "panel · %s con GET fallido: no afirma actualización ni deja controles",
    async (op, boton, confirmar, registrado, overrides) => {
      const spy = stubFetchCola([
        jsonResponse({ acciones: [accionBase(overrides)], count: 1 }),
        jsonResponse({ accion: accionBase(overrides) }),
        jsonResponse({ error: "backend_unavailable" }, 502),
      ]);

      render(<SeccionActionCenter />);
      const dialog = await abrirDetalle(/Plan semanal del negocio/);
      fireEvent.click(within(dialog).getByRole("button", { name: boton }));
      fireEvent.click(within(dialog).getByRole("button", { name: confirmar }));

      const aviso = await within(dialog).findByText(registrado);
      expect(aviso).toHaveTextContent(/No pudimos cargar su estado actualizado/i);
      expect(dialog).not.toHaveTextContent(
        /ya muestra su nuevo estado|Ya está en el historial|Revisa el resultado en el detalle/i,
      );
      expect(within(dialog).getByText(/las decisiones quedan en pausa/i)).toBeInTheDocument();
      // Solo quedan "Actualizar estado" y el cierre del panel.
      const botones = within(dialog)
        .getAllByRole("button")
        .map((b) => b.textContent?.trim() || b.getAttribute("aria-label"));
      expect(botones.sort()).toEqual(["Actualizar estado", "Cerrar"]);
      expect(
        spy.mock.calls.filter(([url]) => url === `/api/automation/acciones/9/${op}`),
      ).toHaveLength(1);
    },
  );

  it.each([
    ["sin respuesta", () => Promise.reject(new TypeError("Failed to fetch"))],
    ["504", () => Promise.resolve(jsonResponse({ error: "backend_timeout" }, 504))],
  ] as const)(
    "HIGH con confirmación %s: no deja reconfirmar sobre el estado sin verificar",
    async (_caso, respuestaConfirmar) => {
      const accion = accionBase({
        id: 55,
        titulo: "Enviar mensaje WhatsApp real",
        riesgo: "high",
        estado: "approved",
        next_required_action: "dedicated_confirmation_required",
      });
      const spy = vi.fn();
      spy.mockResolvedValueOnce(jsonResponse({ acciones: [accion], count: 1 }));
      spy.mockResolvedValueOnce(
        jsonResponse({
          accion_id: 55,
          destino_short: "+5****4567",
          mensaje_preview: "Hola",
          costo_creditos_estimado: 0,
          riesgo: "high",
          confirmacion_requerida: "ENVIAR",
        }),
      );
      spy.mockImplementationOnce(respuestaConfirmar);
      spy.mockResolvedValue(jsonResponse({ error: "backend_unavailable" }, 502));
      vi.stubGlobal("fetch", spy);

      render(<SeccionActionCenter />);
      const dialog = await abrirDetalle(/Enviar mensaje WhatsApp real/);
      fireEvent.click(
        within(dialog).getByRole("button", { name: /Confirmar envío HIGH/i }),
      );
      const input = await within(dialog).findByLabelText(
        /Escribe ENVIAR para confirmar/i,
      );
      fireEvent.change(input, { target: { value: "ENVIAR" } });
      fireEvent.click(
        within(dialog).getByRole("button", { name: /Confirmar y enviar/i }),
      );

      // El resultado del envío es incierto: se intenta leer el estado y,
      // como falla, el panel queda sin verificar y sin controles HIGH.
      await within(dialog).findByText(/las decisiones quedan en pausa/i);
      expect(
        within(dialog).queryByRole("button", { name: /Confirmar y enviar/i }),
      ).not.toBeInTheDocument();
      expect(
        within(dialog).queryByRole("button", { name: /Confirmar envío HIGH/i }),
      ).not.toBeInTheDocument();
      expect(
        spy.mock.calls.filter(
          ([url]) => url === "/api/automation/acciones/55/high-confirmar",
        ),
      ).toHaveLength(1);
    },
  );

  it("tarjeta · HIGH con confirmación 504: relee el estado en vez de dejar reconfirmar", async () => {
    const accion = accionBase({
      id: 55,
      titulo: "Enviar mensaje WhatsApp real",
      riesgo: "high",
      estado: "approved",
      next_required_action: "dedicated_confirmation_required",
    });
    stubFetchCola([
      jsonResponse({ acciones: [accion], count: 1 }),
      jsonResponse({
        accion_id: 55,
        destino_short: "+5****4567",
        mensaje_preview: "Hola",
        costo_creditos_estimado: 0,
        riesgo: "high",
        confirmacion_requerida: "ENVIAR",
      }),
      jsonResponse({ error: "backend_timeout" }, 504),
      // El envío sí se completó en el backend pese al 504.
      jsonResponse({
        acciones: [
          { ...accion, estado: "completed", next_required_action: "none" },
        ],
        count: 1,
      }),
    ]);

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Enviar mensaje WhatsApp real/)).closest(
      "div.surface-card",
    ) as HTMLElement;
    fireEvent.click(
      within(card).getByRole("button", { name: /Confirmar envío HIGH/i }),
    );
    const input = await within(card).findByLabelText(/Escribe ENVIAR para confirmar/i);
    fireEvent.change(input, { target: { value: "ENVIAR" } });
    fireEvent.click(within(card).getByRole("button", { name: /Confirmar y enviar/i }));

    await screen.findByText(/Historial \(1\)/i);
    expect(
      screen.queryByRole("button", { name: /Confirmar y enviar/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Confirmar envío HIGH/i }),
    ).not.toBeInTheDocument();
  });

  it("dice explícitamente cuando una acción cerrada no registró resultado", async () => {
    const accion = accionBase({
      estado: "completed",
      completed_at: "2026-05-10T14:00:00Z",
      result_json: "{}",
    });
    stubFetchCola([jsonResponse({ acciones: [accion], count: 1 })]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);
    expect(
      within(dialog).getByText(/no\s+registró\s+resultado en el payload/i),
    ).toBeInTheDocument();
  });
});

describe("Centro de acción · teclado y accesibilidad", () => {
  it("mueve el foco al bloque de confirmación y lo devuelve al cancelar", async () => {
    stubFetchCola([jsonResponse({ acciones: [accionBase()], count: 1 })]);

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    await waitFor(() =>
      expect(document.activeElement).toHaveTextContent(/¿Aprobar esta acción\?/i),
    );

    fireEvent.click(
      within(dialog).getByRole("button", { name: /^Cancelar$/i }),
    );
    // El botón se vuelve a montar al cerrar la confirmación, así que se
    // compara contra el nodo vivo del DOM.
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(dialog).getByRole("button", { name: /^Aprobar$/i }),
      ),
    );
  });

  it("da un nombre accesible distinto a cada botón Ver detalle", async () => {
    const otra = accionBase({ id: 30, titulo: "Otra acción distinta" });
    stubFetchCola([jsonResponse({ acciones: [accionBase(), otra], count: 2 })]);

    render(<SeccionActionCenter />);
    expect(
      await screen.findByRole("button", {
        name: /Ver detalle de Plan semanal del negocio/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: /Ver detalle de Otra acción distinta/i,
      }),
    ).toBeInTheDocument();
  });

  it("mantiene abierto el historial al filtrar y tras re-renderizar", async () => {
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
    const detalles = document.querySelector("details");
    expect(detalles).not.toBeNull();
    expect((detalles as HTMLDetailsElement).open).toBe(true);

    // Abrir el detalle de una acción re-renderiza la sección: el
    // historial sigue abierto y con el filtro aplicado.
    fireEvent.click(
      screen.getByRole("button", { name: /Ver detalle de Acción rechazada/i }),
    );
    await screen.findByRole("dialog");
    expect((document.querySelector("details") as HTMLDetailsElement).open).toBe(
      true,
    );
    expect(screen.getByText(/Historial \(1 de 2\)/i)).toBeInTheDocument();
  });
});
