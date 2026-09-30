/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-action-center-detalle.test.tsx
//
// Tests del flujo de revisión y decisión del Centro de acción:
//   - el panel lee la acción con GET /api/automation/acciones/:id y solo
//     esa lectura marca el estado como verificado
//   - apertura directa por URL (?accion=<id>) y estados de carga, error y
//     ausente
//   - eventos comprobados de la bitácora, paginados
//   - confirmar antes de aprobar / rechazar / ejecutar, re-verificando el
//     estado justo antes de enviar
//   - POST incierto / GET fallido: sin decisiones sobre datos sin verificar
//   - confirmación dedicada HIGH desde el panel y la tarjeta
//   - teclado y foco

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
  // El panel escribe ?accion=<id> en la URL: cada test empieza limpio.
  window.history.replaceState(null, "", "/dashboard?s=acciones");
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const LISTA = "GET /api/automation/acciones";
const DETALLE = (id = 9) => `GET /api/automation/acciones/${id}`;
const POST = (op: string, id = 9) => `POST /api/automation/acciones/${id}/${op}`;

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

function accionHigh(overrides: Record<string, unknown> = {}) {
  return accionBase({
    id: 55,
    titulo: "Enviar mensaje WhatsApp real",
    tipo_accion: "enviar_mensaje_whatsapp",
    riesgo: "high",
    estado: "approved",
    next_required_action: "dedicated_confirmation_required",
    ...overrides,
  });
}

const PREVIEW_HIGH = {
  ok: true,
  accion_id: 55,
  tipo_accion: "enviar_mensaje_whatsapp",
  titulo: "Enviar mensaje WhatsApp real",
  descripcion: "",
  riesgo: "high",
  estado: "approved",
  costo_creditos_estimado: 5,
  destino_short: "+5****4567",
  numero_destino: "+521****4567",
  mensaje_preview: "Hola Ana, confirmo tu pedido.",
  longitud_mensaje: 29,
  confirmacion_requerida: "ENVIAR",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const lista = (...acciones: unknown[]) =>
  jsonResponse({ acciones, count: acciones.length });

function detalle(
  accion: ReturnType<typeof accionBase>,
  extra: Record<string, unknown> = {},
) {
  return jsonResponse({
    accion,
    eventos: [],
    eventos_hay_mas: false,
    eventos_siguiente_cursor: null,
    eventos_limite: 20,
    leido_en: "2026-05-09T02:00:00Z",
    ...extra,
  });
}

const fallo = (status = 502, error = "backend_unavailable") =>
  jsonResponse({ error }, status);

type Respuesta = Response | Error | (() => Promise<Response>);

/**
 * fetch simulado por ruta ("MÉTODO /ruta", sin query). Cada ruta tiene su
 * cola; la última respuesta se repite. Sin stub: la lista responde vacía y
 * el resto 500, para que ningún test dependa del orden global de llamadas.
 */
function stubRutas(rutas: Record<string, Respuesta[]>) {
  const colas = new Map(Object.entries(rutas).map(([k, v]) => [k, [...v]]));
  const spy = vi.fn(async (url: string, init?: RequestInit) => {
    const clave = `${init?.method ?? "GET"} ${String(url).split("?")[0]}`;
    const cola = colas.get(clave);
    if (!cola || cola.length === 0) {
      return clave === LISTA ? lista() : fallo(500, "sin_stub");
    }
    const r = cola.length > 1 ? cola.shift()! : cola[0];
    if (r instanceof Error) throw r;
    if (typeof r === "function") return r();
    return r.clone();
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const llamadas = (spy: ReturnType<typeof stubRutas>, clave: string) =>
  spy.mock.calls.filter(
    ([url, init]) =>
      `${(init as RequestInit | undefined)?.method ?? "GET"} ${String(url).split("?")[0]}` ===
      clave,
  ).length;

const nunca = () => new Promise<Response>(() => {});

async function abrirDetalle(titulo: RegExp | string) {
  const card = (await screen.findByText(titulo)).closest("div.surface-card");
  const boton = within(card as HTMLElement).getByRole("button", {
    name: /Ver detalle/i,
  });
  fireEvent.click(boton);
  return await screen.findByRole("dialog");
}

/** Abre el panel y espera a que la lectura canónica lo verifique. */
async function abrirVerificado(titulo: RegExp | string) {
  const dialog = await abrirDetalle(titulo);
  await within(dialog).findByText(/Datos actuales/i);
  return dialog;
}

describe("Centro de acción · panel de detalle", () => {
  it("muestra estado, detalle, marcas de tiempo, eventos y resultado legible", async () => {
    const accion = accionBase({
      estado: "completed",
      completed_at: "2026-05-10T14:00:00Z",
      next_required_action: "none",
      result_json: JSON.stringify({ canal: "whatsapp", enviados: 3 }),
    });
    stubRutas({
      [LISTA]: [lista(accion)],
      [DETALLE()]: [
        detalle(accion, {
          eventos: [
            { id: 12, evento: "action_completed", created_at: "2026-05-10T14:00:00Z" },
            { id: 11, evento: "action_created", created_at: "2026-05-09T00:00:00Z" },
          ],
        }),
      ],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);

    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /Completada/,
    );
    expect(within(dialog).getByText(/Detalle de la acción/)).not.toHaveTextContent(
      /sin verificar/i,
    );
    expect(within(dialog).getByText(/Riesgo Medio/i)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Genera un plan semanal a partir del diagnóstico/i),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("generar_plan_semanal")).toBeInTheDocument();
    expect(within(dialog).getByText("diagnostico_a_plan_semanal")).toBeInTheDocument();
    // Marcas de tiempo de la fila + eventos comprobados de la bitácora
    expect(within(dialog).getByText("Creada:")).toBeInTheDocument();
    expect(within(dialog).getByText("Completada:")).toBeInTheDocument();
    const eventos = within(dialog)
      .getByRole("heading", { name: /Eventos comprobados/i })
      .closest("section") as HTMLElement;
    const items = within(eventos).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Acción completada"),
      expect.stringContaining("Acción creada"),
    ]);
    // Resultado en filas, no en JSON crudo
    expect(within(dialog).getByText("canal")).toBeInTheDocument();
    expect(within(dialog).getByText("whatsapp")).toBeInTheDocument();
    expect(within(dialog).getByText("3")).toBeInTheDocument();
    expect(within(dialog).getByText(/ya no admite decisiones/i)).toBeInTheDocument();
  });

  it("mientras verifica muestra el snapshot de la lista y no ofrece decisiones", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [nunca],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);

    expect(within(dialog).getByText(/Último snapshot/i)).toBeInTheDocument();
    expect(
      within(dialog).getByText(/datos de la lista del Centro de acción/i),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /sin verificar/i,
    );
    expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /^Rechazar$/i })).toBeNull();
    expect(within(dialog).getByText(/Cargando eventos/i)).toBeInTheDocument();
    expect(llamadas(spy, DETALLE())).toBe(1);
  });

  it("la lectura canónica manda sobre el snapshot de la lista", async () => {
    // La lista trae un estado viejo; la lectura por id ya lo ve rechazado.
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(
          accionBase({
            estado: "rejected",
            rejected_at: "2026-05-09T01:30:00Z",
            next_required_action: "none",
          }),
        ),
      ],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /Rechazada/,
    );
    expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
  });

  it("aprobar exige confirmación, re-verifica y solo entonces llama al backend", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(accionBase()),
        detalle(accionBase()),
        detalle(accionBase({ estado: "approved", next_required_action: "execute_available" })),
      ],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    expect(within(dialog).getByText(/¿Aprobar esta acción\?/i)).toBeInTheDocument();
    expect(llamadas(spy, POST("aprobar"))).toBe(0);
    const lecturasAntes = llamadas(spy, DETALLE());

    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));
    await waitFor(() => expect(llamadas(spy, POST("aprobar"))).toBe(1));
    // Una lectura justo antes del POST y otra después.
    await waitFor(() => expect(llamadas(spy, DETALLE())).toBe(lecturasAntes + 2));
    const exito = await within(dialog).findByRole("status");
    expect(exito).toHaveTextContent(
      "Acción aprobada. El panel ya muestra su estado verificado.",
    );
    expect(
      within(dialog).getByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    ).toBeInTheDocument();
  });

  it("tras confirmar, el foco pasa al mensaje de resultado y no se pierde en el diálogo", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(accionBase()),
        detalle(accionBase()),
        detalle(accionBase({ estado: "approved", next_required_action: "execute_available" })),
      ],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    const exito = await within(dialog).findByRole("status");
    await waitFor(() => expect(document.activeElement).toBe(exito));
  });

  it("no envía la decisión si la acción cambió desde que se abrió el panel", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(accionBase()),
        // Entre la apertura y la confirmación alguien la rechazó.
        detalle(
          accionBase({
            estado: "rejected",
            updated_at: "2026-05-09T01:45:00Z",
            next_required_action: "none",
          }),
        ),
      ],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    expect(
      await within(dialog).findByText(/cambió mientras la revisabas/i),
    ).toBeInTheDocument();
    expect(llamadas(spy, POST("aprobar"))).toBe(0);
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /Rechazada/,
    );
  });

  it("no envía la decisión si no puede verificar el estado justo antes", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase()), fallo(504, "backend_timeout")],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Rechazar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, rechazar/i }));

    const alerta = await within(dialog).findByRole("alert");
    expect(alerta).toHaveTextContent(/tu decisión no se envió/i);
    expect(llamadas(spy, POST("rechazar"))).toBe(0);
    expect(within(dialog).getByText(/las decisiones quedan en pausa/i)).toBeInTheDocument();
  });

  it("si el backend acepta pero el estado verificado no cambió, no afirma la decisión", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase()), detalle(accionBase()), detalle(accionBase())],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase() })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    const aviso = await within(dialog).findByText(/El servidor respondió/i);
    expect(aviso).toHaveTextContent(/sigue en «Esperando tu aprobación»/);
    expect(within(dialog).queryByText(/^Acción aprobada\./)).toBeNull();
  });

  it("rechazar pide confirmación desde la tarjeta antes de llamar al backend", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase()), lista()],
      [POST("rechazar")]: [jsonResponse({ accion: accionBase({ estado: "rejected" }) })],
    });

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Plan semanal del negocio/)).closest(
      "div.surface-card",
    ) as HTMLElement;

    fireEvent.click(within(card).getByRole("button", { name: /Rechazar/i }));
    expect(within(card).getByText(/¿Rechazar esta acción\?/i)).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: /^Cancelar$/i }));
    expect(llamadas(spy, POST("rechazar"))).toBe(0);

    fireEvent.click(within(card).getByRole("button", { name: /Rechazar/i }));
    fireEvent.click(within(card).getByRole("button", { name: /Sí, rechazar/i }));
    await waitFor(() => expect(llamadas(spy, POST("rechazar"))).toBe(1));
  });

  it("ejecutar dry-run confirma y anuncia el resultado por aria-live", async () => {
    const accion = accionBase({
      estado: "pending",
      riesgo: "low",
      requires_approval: false,
      next_required_action: "execute_available",
    });
    const spy = stubRutas({
      [LISTA]: [lista(accion)],
      [POST("ejecutar")]: [jsonResponse({ accion })],
    });

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Plan semanal del negocio/)).closest(
      "div.surface-card",
    ) as HTMLElement;

    fireEvent.click(within(card).getByRole("button", { name: /Ejecutar \(dry-run\)/i }));
    expect(within(card).getByText(/dry-run/i)).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: /Sí, ejecutar/i }));
    await waitFor(() => expect(llamadas(spy, POST("ejecutar"))).toBe(1));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/Ejecución dry-run registrada/i),
    );
  });
});

describe("Centro de acción · apertura directa por URL", () => {
  it("abre el detalle de ?accion=<id> aunque no esté en la lista", async () => {
    window.history.replaceState(null, "", "/dashboard?s=acciones&accion=77");
    const spy = stubRutas({
      [LISTA]: [lista()],
      [DETALLE(77)]: [detalle(accionBase({ id: 77, titulo: "Acción enlazada" }))],
    });

    render(<SeccionActionCenter />);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Acción enlazada")).toBeInTheDocument();
    expect(within(dialog).getByText(/Datos actuales/i)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: /^Aprobar$/i })).toBeInTheDocument();
    expect(spy).toHaveBeenCalledWith(
      "/api/automation/acciones/77",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("mientras lee sin snapshot muestra un estado de carga anunciado", async () => {
    window.history.replaceState(null, "", "/dashboard?s=acciones&accion=77");
    stubRutas({ [LISTA]: [lista()], [DETALLE(77)]: [nunca] });

    render(<SeccionActionCenter />);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Cargando acción")).toBeInTheDocument();
    expect(within(dialog).getByRole("status")).toHaveTextContent(
      /Leyendo el estado actual/i,
    );
    expect(dialog).toHaveAttribute("aria-busy", "true");
    expect(within(dialog).getAllByRole("button").map((b) => b.getAttribute("aria-label"))).toEqual([
      "Cerrar",
    ]);
  });

  it("ignora ?accion= que no es un id válido", async () => {
    window.history.replaceState(null, "", "/dashboard?s=acciones&accion=12abc");
    const spy = stubRutas({ [LISTA]: [lista(accionBase())] });

    render(<SeccionActionCenter />);
    await screen.findByText(/Plan semanal del negocio/);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(spy.mock.calls.every(([url]) => url === "/api/automation/acciones")).toBe(true);
  });

  it("abrir escribe ?accion=<id> en la URL y cerrar lo quita", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase())],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    const url = new URL(window.location.href);
    expect(url.searchParams.get("accion")).toBe("9");
    expect(url.searchParams.get("s")).toBe("acciones");

    fireEvent.click(within(dialog).getByRole("button", { name: "Cerrar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(new URL(window.location.href).searchParams.get("accion")).toBeNull();
  });

  it("404: dice que la acción no está disponible y no muestra datos ni decisiones", async () => {
    window.history.replaceState(null, "", "/dashboard?s=acciones&accion=404");
    stubRutas({
      [LISTA]: [lista()],
      [DETALLE(404)]: [fallo(404, "accion_not_found")],
    });

    render(<SeccionActionCenter />);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Acción no disponible")).toBeInTheDocument();
    expect(within(dialog).getByText(/no está asociada a tu cuenta/i)).toBeInTheDocument();
    const botones = within(dialog)
      .getAllByRole("button")
      .map((b) => b.textContent?.trim() || b.getAttribute("aria-label"));
    expect(botones.sort()).toEqual(["Cerrar", "Volver al Centro de acción"]);
  });

  it("error sin snapshot: explica el fallo y permite reintentar", async () => {
    window.history.replaceState(null, "", "/dashboard?s=acciones&accion=9");
    stubRutas({
      [LISTA]: [lista()],
      [DETALLE()]: [fallo(502), detalle(accionBase())],
    });

    render(<SeccionActionCenter />);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("No pudimos cargar la acción")).toBeInTheDocument();
    expect(within(dialog).getByRole("alert")).toHaveTextContent(
      /servicio de automatización no está disponible/i,
    );
    fireEvent.click(within(dialog).getByRole("button", { name: /Reintentar/i }));
    expect(await within(dialog).findByText(/Datos actuales/i)).toBeInTheDocument();
  });

  it("al cerrar un panel abierto por URL el foco va al título de la sección", async () => {
    window.history.replaceState(null, "", "/dashboard?s=acciones&accion=9");
    stubRutas({
      [LISTA]: [lista()],
      [DETALLE()]: [detalle(accionBase())],
    });

    render(<SeccionActionCenter />);
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText(/Datos actuales/i);
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("heading", { name: /Centro de acción/i }),
      ),
    );
  });
});

describe("Centro de acción · eventos comprobados", () => {
  it("pagina la bitácora con el cursor y lleva el foco al primer evento nuevo", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(accionBase(), {
          eventos: [
            { id: 40, evento: "action_approved", created_at: "2026-05-09T01:00:00Z" },
            { id: 39, evento: "evento_futuro_x", created_at: null },
          ],
          eventos_hay_mas: true,
          eventos_siguiente_cursor: 39,
        }),
        detalle(accionBase(), {
          eventos: [
            { id: 38, evento: "action_created", created_at: "2026-05-09T00:00:00Z" },
          ],
        }),
      ],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    const seccion = within(dialog)
      .getByRole("heading", { name: /Eventos comprobados/i })
      .closest("section") as HTMLElement;
    // Evento desconocido: no se disfraza, se muestra su código.
    expect(within(seccion).getByText("evento_futuro_x")).toBeInTheDocument();
    expect(within(seccion).getByText(/Sin fecha registrada/i)).toBeInTheDocument();

    fireEvent.click(
      within(seccion).getByRole("button", { name: /Cargar eventos anteriores/i }),
    );
    expect(await within(seccion).findByText("Acción creada")).toBeInTheDocument();
    expect(spy).toHaveBeenCalledWith(
      "/api/automation/acciones/9?eventos_antes_de=39",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(within(seccion).getAllByRole("listitem")).toHaveLength(3);
    expect(
      within(seccion).queryByRole("button", { name: /Cargar eventos anteriores/i }),
    ).toBeNull();
    await waitFor(() =>
      expect(document.activeElement).toHaveTextContent("Acción creada"),
    );
  });

  it("explica la bitácora vacía sin inventar eventos", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase())],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    expect(
      within(dialog).getByText(/La bitácora no tiene eventos registrados/i),
    ).toBeInTheDocument();
  });

  it("si la lectura falla no muestra eventos ni los sustituye por marcas de tiempo", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [fallo(502)],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirDetalle(/Plan semanal del negocio/);
    expect(
      await within(dialog).findByText(/No pudimos cargar la bitácora/i),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/Último snapshot · sin verificar/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/viene de la lista del Centro de acción/i)).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
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
    stubRutas({ [LISTA]: [lista(completada, rechazada)] });

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
      next_required_action: "none",
      error_message: "El usuario no quiso continuar",
    });
    stubRutas({
      [LISTA]: [lista(rechazada)],
      [DETALLE(22)]: [detalle(rechazada)],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Acción rechazada/);
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(/Rechazada/);
    expect(within(dialog).getByText("Rechazada:")).toBeInTheDocument();
    expect(within(dialog).getByText(/El usuario no quiso continuar/i)).toBeInTheDocument();
  });
});

describe("Centro de acción · confirmación HIGH desde el panel", () => {
  it("pide preview y confirmación literal ENVIAR y relee la acción", async () => {
    const accion = accionHigh({
      execution_block_reason: "Requiere preview y confirmación literal.",
    });
    const spy = stubRutas({
      [LISTA]: [lista(accion)],
      [DETALLE(55)]: [
        detalle(accion),
        detalle(accionHigh({ estado: "completed", next_required_action: "none" })),
      ],
      [POST("high-preview", 55)]: [jsonResponse(PREVIEW_HIGH)],
      [POST("high-confirmar", 55)]: [
        jsonResponse({ accion: { ...accion, estado: "completed" }, ejecucion: { estado_final: "completed" } }),
      ],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Enviar mensaje WhatsApp real/);

    fireEvent.click(within(dialog).getByRole("button", { name: /Confirmar envío HIGH/i }));
    await within(dialog).findByText(/Preview de envío HIGH/i);
    expect(within(dialog).getByText(/\+5\*\*\*\*4567/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Hola Ana, confirmo tu pedido/i)).toBeInTheDocument();

    const input = within(dialog).getByLabelText(/Escribe ENVIAR para confirmar/i);
    fireEvent.change(input, { target: { value: "enviar" } });
    expect(within(dialog).getByRole("button", { name: /Confirmar y enviar/i })).toBeDisabled();

    fireEvent.change(input, { target: { value: "ENVIAR" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirmar y enviar/i }));
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        "/api/automation/acciones/55/high-confirmar",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ confirmacion: "ENVIAR" }),
        }),
      ),
    );
    expect(
      await within(dialog).findByText(
        "Confirmación HIGH registrada. El panel ya muestra su estado verificado.",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(/Completada/);
  });
});

describe("Centro de acción · estados del panel (error, éxito, vacío)", () => {
  it("muestra el error real del backend en el panel y no duplica el anuncio global", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase())],
      [POST("aprobar")]: [fallo(409, "high_confirmation_not_available")],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    const alerta = await within(dialog).findByRole("alert");
    expect(alerta).toHaveTextContent(/ya no admite esta confirmación/i);
    // El panel es la superficie que decide: la región global queda vacía.
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("si falla el refresco de la lista, el panel sigue verificado con su propia lectura", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase()), fallo(502)],
      [DETALLE()]: [
        detalle(accionBase()),
        detalle(accionBase()),
        detalle(accionBase({ estado: "approved", next_required_action: "execute_available" })),
      ],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    expect(
      await within(dialog).findByText(/El panel ya muestra su estado verificado/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(within(dialog).getByText(/Datos actuales/i)).toBeInTheDocument();
  });

  it("POST exitoso + GET fallido: decisión registrada, estado sin verificar y sin repetir la decisión", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(accionBase()),
        detalle(accionBase()),
        fallo(502),
        detalle(
          accionBase({
            estado: "approved",
            approved_at: "2026-05-09T02:00:00Z",
            next_required_action: "execute_available",
          }),
        ),
      ],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    const aviso = await within(dialog).findByText(/Acción aprobada\./i);
    expect(aviso).toHaveAttribute("role", "status");
    expect(aviso).toHaveTextContent(/No pudimos cargar su estado actualizado/i);
    expect(aviso).not.toHaveTextContent(/estado verificado/i);
    expect(within(dialog).getByText(/Detalle de la acción/)).toHaveTextContent(
      /sin verificar/i,
    );
    expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /^Rechazar$/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /Ejecutar/i })).toBeNull();
    expect(llamadas(spy, POST("aprobar"))).toBe(1);

    fireEvent.click(within(dialog).getByRole("button", { name: /Actualizar estado/i }));
    expect(
      await within(dialog).findByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    ).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
    expect(within(dialog).queryByText(/No pudimos confirmar el estado actual/i)).toBeNull();
    expect(within(dialog).queryByText(/Acción aprobada\./i)).toBeNull();
    expect(llamadas(spy, POST("aprobar"))).toBe(1);
  });

  it("si Actualizar estado vuelve a fallar, las decisiones siguen en pausa", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [
        detalle(accionBase()),
        detalle(accionBase()),
        fallo(502),
        fallo(504, "backend_timeout"),
      ],
      [POST("rechazar")]: [jsonResponse({ accion: accionBase({ estado: "rejected" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Rechazar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, rechazar/i }));
    await within(dialog).findByText(/Acción rechazada\./i);

    fireEvent.click(within(dialog).getByRole("button", { name: /Actualizar estado/i }));
    const alerta = await within(dialog).findByRole("alert");
    expect(alerta).toHaveTextContent(/Seguimos sin poder cargar el estado/i);
    expect(within(dialog).queryByRole("button", { name: /^Rechazar$/i })).toBeNull();
    expect(within(dialog).getByRole("button", { name: /Actualizar estado/i })).toBeInTheDocument();
  });

  it("HIGH confirmada + GET fallido no afirma estado ni reofrece la confirmación", async () => {
    const spy = stubRutas({
      [LISTA]: [lista(accionHigh())],
      [DETALLE(55)]: [detalle(accionHigh()), fallo(502)],
      [POST("high-preview", 55)]: [jsonResponse(PREVIEW_HIGH)],
      [POST("high-confirmar", 55)]: [jsonResponse({ accion: accionHigh({ estado: "completed" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Enviar mensaje WhatsApp real/);
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirmar envío HIGH/i }));
    const input = await within(dialog).findByLabelText(/Escribe ENVIAR para confirmar/i);
    fireEvent.change(input, { target: { value: "ENVIAR" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Confirmar y enviar/i }));

    const aviso = await within(dialog).findByText(/Confirmación HIGH registrada\./i);
    expect(aviso).toHaveTextContent(/No pudimos cargar su estado actualizado/i);
    expect(within(dialog).queryByRole("button", { name: /Confirmar envío HIGH/i })).toBeNull();
    expect(llamadas(spy, POST("high-confirmar", 55))).toBe(1);
  });

  it.each([
    ["con GET fallido", fallo(502), /las decisiones quedan en pausa/i],
    [
      "con estado real legible",
      detalle(accionBase({ estado: "approved", next_required_action: "execute_available" })),
      /Datos actuales/i,
    ],
  ] as const)(
    "POST sin respuesta %s: avisa que la decisión es incierta y no la reofrece",
    async (_caso, lecturaPosterior, textoFuente) => {
      const spy = stubRutas({
        [LISTA]: [lista(accionBase())],
        [DETALLE()]: [detalle(accionBase()), detalle(accionBase()), lecturaPosterior],
        [POST("aprobar")]: [new TypeError("Failed to fetch")],
      });

      render(<SeccionActionCenter />);
      const dialog = await abrirVerificado(/Plan semanal del negocio/);
      fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
      fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

      const alerta = await within(dialog).findByRole("alert");
      expect(alerta).toHaveTextContent(/no sabemos si se registró/i);
      expect(within(dialog).getByText(textoFuente)).toBeInTheDocument();
      expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
      expect(llamadas(spy, POST("aprobar"))).toBe(1);
    },
  );

  it("desde la tarjeta: POST exitoso + GET fallido no anuncia la lista como actualizada", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase()), fallo(502)],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

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
    expect(screen.getByText(/No pudimos cargar tus acciones/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Aprobar$/i })).not.toBeInTheDocument();
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
      const spy = stubRutas({
        [LISTA]: [lista(accionBase(overrides))],
        [DETALLE()]: [detalle(accionBase(overrides)), detalle(accionBase(overrides)), fallo(502)],
        [POST(op)]: [jsonResponse({ accion: accionBase(overrides) })],
      });

      render(<SeccionActionCenter />);
      const dialog = await abrirVerificado(/Plan semanal del negocio/);
      fireEvent.click(within(dialog).getByRole("button", { name: boton }));
      fireEvent.click(within(dialog).getByRole("button", { name: confirmar }));

      const aviso = await within(dialog).findByText(registrado);
      expect(aviso).toHaveTextContent(/No pudimos cargar su estado actualizado/i);
      expect(dialog).not.toHaveTextContent(/estado verificado/i);
      expect(within(dialog).getByText(/las decisiones quedan en pausa/i)).toBeInTheDocument();
      // Solo quedan "Actualizar estado" y el cierre del panel.
      const botones = within(dialog)
        .getAllByRole("button")
        .map((b) => b.textContent?.trim() || b.getAttribute("aria-label"));
      expect(botones.sort()).toEqual(["Actualizar estado", "Cerrar"]);
      expect(llamadas(spy, POST(op))).toBe(1);
    },
  );

  it.each([
    ["sin respuesta", new TypeError("Failed to fetch")],
    ["504", fallo(504, "backend_timeout")],
  ] as const)(
    "HIGH con confirmación %s: no deja reconfirmar sobre el estado sin verificar",
    async (_caso, respuestaConfirmar) => {
      const spy = stubRutas({
        [LISTA]: [lista(accionHigh())],
        [DETALLE(55)]: [detalle(accionHigh()), fallo(502)],
        [POST("high-preview", 55)]: [jsonResponse(PREVIEW_HIGH)],
        [POST("high-confirmar", 55)]: [respuestaConfirmar],
      });

      render(<SeccionActionCenter />);
      const dialog = await abrirVerificado(/Enviar mensaje WhatsApp real/);
      fireEvent.click(within(dialog).getByRole("button", { name: /Confirmar envío HIGH/i }));
      const input = await within(dialog).findByLabelText(/Escribe ENVIAR para confirmar/i);
      fireEvent.change(input, { target: { value: "ENVIAR" } });
      fireEvent.click(within(dialog).getByRole("button", { name: /Confirmar y enviar/i }));

      await within(dialog).findByText(/las decisiones quedan en pausa/i);
      expect(within(dialog).queryByRole("button", { name: /Confirmar y enviar/i })).toBeNull();
      expect(within(dialog).queryByRole("button", { name: /Confirmar envío HIGH/i })).toBeNull();
      expect(llamadas(spy, POST("high-confirmar", 55))).toBe(1);
    },
  );

  it("tarjeta · HIGH con confirmación 504: relee el estado en vez de dejar reconfirmar", async () => {
    stubRutas({
      [LISTA]: [
        lista(accionHigh()),
        // El envío sí se completó en el backend pese al 504.
        lista(accionHigh({ estado: "completed", next_required_action: "none" })),
      ],
      [POST("high-preview", 55)]: [jsonResponse(PREVIEW_HIGH)],
      [POST("high-confirmar", 55)]: [fallo(504, "backend_timeout")],
    });

    render(<SeccionActionCenter />);
    const card = (await screen.findByText(/Enviar mensaje WhatsApp real/)).closest(
      "div.surface-card",
    ) as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: /Confirmar envío HIGH/i }));
    const input = await within(card).findByLabelText(/Escribe ENVIAR para confirmar/i);
    fireEvent.change(input, { target: { value: "ENVIAR" } });
    fireEvent.click(within(card).getByRole("button", { name: /Confirmar y enviar/i }));

    await screen.findByText(/Historial \(1\)/i);
    expect(screen.queryByRole("button", { name: /Confirmar y enviar/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Confirmar envío HIGH/i })).toBeNull();
  });

  it("tras decidir con GET fallido, lleva Actualizar estado a la vista y le da el foco", async () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase()), detalle(accionBase()), fallo(502)],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    scroll.mockClear();
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    const actualizar = await within(dialog).findByRole("button", {
      name: /Actualizar estado/i,
    });
    await waitFor(() => expect(document.activeElement).toBe(actualizar));
    expect(scroll.mock.contexts).toContain(actualizar);
  });

  it("si tras decidir la lectura da 404, dice que la acción ya no está disponible", async () => {
    stubRutas({
      [LISTA]: [lista(accionBase())],
      [DETALLE()]: [detalle(accionBase()), detalle(accionBase()), fallo(404, "accion_not_found")],
      [POST("aprobar")]: [jsonResponse({ accion: accionBase({ estado: "approved" }) })],
    });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Sí, aprobar/i }));

    expect(await within(dialog).findByText("Acción no disponible")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /^Aprobar$/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /^Rechazar$/i })).toBeNull();
  });

  it("dice explícitamente cuando una acción cerrada no registró resultado", async () => {
    const accion = accionBase({
      estado: "completed",
      completed_at: "2026-05-10T14:00:00Z",
      next_required_action: "none",
      result_json: "{}",
    });
    stubRutas({ [LISTA]: [lista(accion)], [DETALLE()]: [detalle(accion)] });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);
    expect(
      within(dialog).getByText(/no\s+registró\s+resultado en el payload/i),
    ).toBeInTheDocument();
  });
});

describe("Centro de acción · teclado y accesibilidad", () => {
  it("mueve el foco al bloque de confirmación y lo devuelve al cancelar", async () => {
    stubRutas({ [LISTA]: [lista(accionBase())], [DETALLE()]: [detalle(accionBase())] });

    render(<SeccionActionCenter />);
    const dialog = await abrirVerificado(/Plan semanal del negocio/);

    fireEvent.click(within(dialog).getByRole("button", { name: /^Aprobar$/i }));
    await waitFor(() =>
      expect(document.activeElement).toHaveTextContent(/¿Aprobar esta acción\?/i),
    );
    fireEvent.click(within(dialog).getByRole("button", { name: /^Cancelar$/i }));
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(dialog).getByRole("button", { name: /^Aprobar$/i }),
      ),
    );
  });

  it.each([
    ["Escape", (dialog: HTMLElement) => fireEvent.keyDown(dialog, { key: "Escape" })],
    [
      "botón Cerrar",
      (dialog: HTMLElement) =>
        fireEvent.click(within(dialog).getByRole("button", { name: "Cerrar" })),
    ],
  ] as const)(
    "al cerrar con %s el foco vuelve al Ver detalle que abrió el panel",
    async (_via, cerrar) => {
      const otra = accionBase({ id: 30, titulo: "Otra acción distinta" });
      stubRutas({
        [LISTA]: [lista(otra, accionBase())],
        [DETALLE()]: [detalle(accionBase())],
      });

      render(<SeccionActionCenter />);
      const disparador = await screen.findByRole("button", {
        name: /Ver detalle de Plan semanal del negocio/i,
      });
      disparador.focus();
      fireEvent.click(disparador);
      const dialog = await screen.findByRole("dialog");
      await within(dialog).findByText(/Datos actuales/i);

      cerrar(dialog);
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      await waitFor(() =>
        expect(document.activeElement).toBe(
          screen.getByRole("button", { name: /Ver detalle de Plan semanal del negocio/i }),
        ),
      );
    },
  );

  it("da un nombre accesible distinto a cada botón Ver detalle", async () => {
    const otra = accionBase({ id: 30, titulo: "Otra acción distinta" });
    stubRutas({ [LISTA]: [lista(accionBase(), otra)] });

    render(<SeccionActionCenter />);
    expect(
      await screen.findByRole("button", { name: /Ver detalle de Plan semanal del negocio/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Ver detalle de Otra acción distinta/i }),
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
    stubRutas({
      [LISTA]: [lista(completada, rechazada)],
      [DETALLE(22)]: [detalle(rechazada)],
    });

    render(<SeccionActionCenter />);
    await screen.findByText(/Historial \(2\)/i);

    fireEvent.click(screen.getByRole("button", { name: /Rechazadas/i }));
    const detalles = document.querySelector("details");
    expect(detalles).not.toBeNull();
    expect((detalles as HTMLDetailsElement).open).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: /Ver detalle de Acción rechazada/i }));
    await screen.findByRole("dialog");
    expect((document.querySelector("details") as HTMLDetailsElement).open).toBe(true);
    expect(screen.getByText(/Historial \(1 de 2\)/i)).toBeInTheDocument();
  });
});
