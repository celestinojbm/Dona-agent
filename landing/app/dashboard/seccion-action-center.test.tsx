/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-action-center.test.tsx
//
// Hotfix T2.1.B: tests de UI para verificar que el componente:
//   - muestra empty state cuando backend retorna lista vacía
//   - muestra empty state cuando hay sub no persistida (route handler
//     ya convierte 404 backend → 200 [])
//   - muestra error real solo ante 4xx/5xx genuinos
//   - mantiene el botón "Generar acciones" en TODOS los estados
//   - botón generar funciona aún cuando lista inicial está vacía/error

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionActionCenter from "./seccion-action-center";

afterEach(() => {
  cleanup();  // desmontar el árbol React entre tests · evita
              // 'Found multiple elements' por containers acumulados
  vi.restoreAllMocks();
});

beforeEach(() => {
  // jsdom no provee window.alert · stub
  vi.stubGlobal("alert", vi.fn());
});


function mockFetchOnce(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response));
}


describe("SeccionActionCenter · empty state", () => {
  it("backend devuelve lista vacía → muestra empty state con CTA", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [], count: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/Aún no hay acciones generadas/i),
      ).toBeInTheDocument(),
    );
    // Botón en empty state
    const botones = screen.getAllByRole("button", {
      name: /Generar acciones/i,
    });
    expect(botones.length).toBeGreaterThan(0);
  });

  it("subscription_no_persistida → route handler convierte a 200 [] → empty state", async () => {
    // Simulamos lo que el route handler ahora retorna en ese caso
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [], count: 0 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/Aún no hay acciones generadas/i),
      ).toBeInTheDocument(),
    );
  });
});


describe("SeccionActionCenter · error real (5xx)", () => {
  it("502 → muestra error con código + ofrece reintentar y generar", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ error: "backend_unavailable" }), {
        status: 502,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/No pudimos cargar tus acciones/i),
      ).toBeInTheDocument(),
    );
    // Código del error visible
    expect(screen.getByText(/error_502/i)).toBeInTheDocument();
    // Botón Reintentar disponible
    expect(
      screen.getByRole("button", { name: /Reintentar/i }),
    ).toBeInTheDocument();
    // Botón Generar acciones DEBE seguir disponible (en error real
    // también, después del hotfix · al menos uno en la cabecera)
    const botonesGenerar = screen.getAllByRole("button", {
      name: /Generar acciones/i,
    });
    expect(botonesGenerar.length).toBeGreaterThanOrEqual(1);
  });

  it("504 timeout → muestra error con código y opción de reintentar", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ error: "backend_timeout" }), {
        status: 504,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/error_504/i)).toBeInTheDocument(),
    );
  });
});


describe("SeccionActionCenter · loading inicial", () => {
  it("antes de la primera respuesta muestra Cargando…", async () => {
    // Promise nunca se resuelve durante el render
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    render(<SeccionActionCenter />);
    expect(screen.getByText(/Cargando…/i)).toBeInTheDocument();
  });
});


describe("SeccionActionCenter · perfil insuficiente (hotfix)", () => {
  it("tras generar y recibir perfil_estado=missing muestra banner con CTA WhatsApp", async () => {
    // Mock: 1) initial GET acciones devuelve [] · 2) POST generar
    // devuelve perfil_estado=missing · 3) refetch GET sigue []
    const fetchSpy = vi.fn()
      .mockResolvedValueOnce(  // 1) initial GET
        new Response(JSON.stringify({ acciones: [], count: 0 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(  // 2) POST generar
        new Response(JSON.stringify({
          oportunidades_evaluadas: 0,
          acciones: [],
          perfil_estado: "missing",
          perfil_campos_llenos: 0,
          perfil_campos_totales: 6,
          perfil_razon: "Aún no encontramos tu perfil de negocio.",
          perfil_siguiente_paso: "Escribe 'empezar diagnóstico' a Dona por WhatsApp.",
        }), { status: 200 }),
      )
      .mockResolvedValueOnce(  // 3) refetch GET acciones
        new Response(JSON.stringify({ acciones: [], count: 0 }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchSpy);

    render(<SeccionActionCenter />);
    // Esperar empty inicial
    await waitFor(() =>
      expect(
        screen.getByText("Aún no hay acciones generadas."),
      ).toBeInTheDocument(),
    );
    // Click en el botón del empty state · usar findAll y tomar el primero
    const botones = screen.getAllByRole("button", {
      name: /Generar acciones desde tu diagnóstico/i,
    });
    botones[0].click();

    // Tras la respuesta debe aparecer banner de Diagnóstico pendiente
    await waitFor(() =>
      expect(screen.getByText(/Diagnóstico pendiente/i)).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/Aún no encontramos tu perfil de negocio/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Abrir WhatsApp/i }),
    ).toBeInTheDocument();
  });

  it("perfil_estado=incomplete muestra contador de campos llenos", async () => {
    const fetchSpy = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ acciones: [], count: 0 }), {
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          oportunidades_evaluadas: 0,
          acciones: [],
          perfil_estado: "incomplete",
          perfil_campos_llenos: 1,
          perfil_campos_totales: 6,
          perfil_razon: "Tienes 1 de 6 campos llenos.",
          perfil_siguiente_paso: "Continúa el diagnóstico con Dona.",
        }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ acciones: [], count: 0 }), {
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchSpy);

    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/Aún no hay acciones/i)).toBeInTheDocument(),
    );
    const botones = screen.getAllByRole("button", {
      name: /Generar acciones/i,
    });
    botones[botones.length - 1].click();
    await waitFor(() =>
      expect(
        screen.getByText(/Diagnóstico incompleto/i),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/1\/6/)).toBeInTheDocument();
  });
});


describe("SeccionActionCenter · acciones presentes", () => {
  it("renderiza acción LOW pending con botón Ejecutar (dry-run)", async () => {
    const accion = {
      id: 1,
      opportunity_id: "opp_1",
      playbook_id: "diagnostico_a_plan_semanal",
      tipo_accion: "generar_plan_semanal",
      titulo: "Plan semanal de prueba",
      descripcion: "Genera un plan semanal",
      razon_recomendacion: "Tu diagnóstico está completo",
      estado: "pending",
      riesgo: "low",
      costo_creditos_estimado: 8,
      requires_approval: false,
      result_json: "{}",
      error_message: "",
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T00:00:00Z",
      approved_at: null,
      rejected_at: null,
      completed_at: null,
    };
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/Plan semanal de prueba/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/Bajo/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    ).toBeInTheDocument();
  });

  it("renderiza acción HIGH approved como pendiente de confirmación dedicada", async () => {
    // Guardrail UX: una HIGH aprobada NO debe verse como "lista para
    // ejecutar" en este control genérico. Debe reflejar que aún falta
    // una UX de confirmación dedicada (preview, costo, riesgo,
    // confirmación fuerte) antes de cualquier efecto externo real, y
    // NO debe ofrecer el botón "Ejecutar".
    const accion = {
      id: 3,
      opportunity_id: "opp_3",
      playbook_id: "whatsapp_outbound",
      tipo_accion: "enviar_mensaje_whatsapp",
      titulo: "Enviar mensaje WhatsApp",
      descripcion: "Manda un mensaje aprobado a un cliente",
      razon_recomendacion: "El cliente quedó en confirmar",
      estado: "approved",
      riesgo: "high",
      costo_creditos_estimado: 5,
      requires_approval: true,
      result_json: "{}",
      error_message: "",
      created_at: "2026-05-24T00:00:00Z",
      updated_at: "2026-05-24T00:00:00Z",
      approved_at: "2026-05-24T00:00:01Z",
      rejected_at: null,
      completed_at: null,
    };
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(
        screen.getByText(/Enviar mensaje WhatsApp/),
      ).toBeInTheDocument(),
    );
    // Etiqueta de estado refleja el siguiente paso, no "lista para ejecutar"
    expect(
      screen.getByText(/Aprobada · requiere confirmación dedicada/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Aprobada · lista para ejecutar/i),
    ).not.toBeInTheDocument();
    // Botón dedicado del próximo paso
    expect(
      screen.getByRole("button", { name: /Confirmar envío HIGH/i }),
    ).toBeInTheDocument();
    // El aviso explicativo sigue presente
    expect(
      screen.getByText(/necesita\s+confirmación dedicada/i),
    ).toBeInTheDocument();
    // NO debe ofrecer el botón "Ejecutar" en este control genérico
    expect(
      screen.queryByRole("button", { name: /Ejecutar \(dry-run\)/i }),
    ).not.toBeInTheDocument();
  });

  it("confirmación dedicada HIGH muestra preview y exige ENVIAR exacto", async () => {
    const accion = {
      id: 55,
      opportunity_id: "opp_55",
      playbook_id: "whatsapp_outbound",
      tipo_accion: "enviar_mensaje_whatsapp",
      titulo: "Enviar mensaje WhatsApp real",
      descripcion: "Manda un mensaje aprobado a un cliente",
      razon_recomendacion: "",
      estado: "approved",
      riesgo: "high",
      costo_creditos_estimado: 5,
      requires_approval: true,
      result_json: "{}",
      error_message: "",
      created_at: "2026-05-24T00:00:00Z",
      updated_at: "2026-05-24T00:00:00Z",
      approved_at: "2026-05-24T00:00:01Z",
      rejected_at: null,
      completed_at: null,
      next_required_action: "dedicated_confirmation_required",
      execution_block_reason: "Requiere preview y confirmación literal.",
    };
    const completada = { ...accion, estado: "completed", result_json: "{}" };
    const fetchSpy = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ acciones: [accion], count: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ok: true,
        accion_id: 55,
        tipo_accion: "enviar_mensaje_whatsapp",
        titulo: "Enviar mensaje WhatsApp real",
        descripcion: "Manda un mensaje aprobado a un cliente",
        riesgo: "high",
        estado: "approved",
        costo_creditos_estimado: 5,
        destino_short: "+5****4567",
        numero_destino: "+5215551234567",
        mensaje_preview: "Hola Ana, confirmo tu pedido.",
        longitud_mensaje: 29,
        confirmacion_requerida: "ENVIAR",
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ accion: completada, ejecucion: { estado_final: "completed" } }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ acciones: [completada], count: 1 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);

    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/Enviar mensaje WhatsApp real/)).toBeInTheDocument(),
    );
    screen.getByRole("button", { name: /Confirmar envío HIGH/i }).click();
    await waitFor(() =>
      expect(screen.getByText(/Preview de envío HIGH/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/\+5\*\*\*\*4567/)).toBeInTheDocument();
    expect(screen.getByText(/Hola Ana, confirmo tu pedido/i)).toBeInTheDocument();

    const input = screen.getByLabelText(/Escribe ENVIAR para confirmar/i);
    fireEvent.change(input, { target: { value: " ENVIAR " } });
    expect(
      screen.getByRole("button", { name: /Confirmar y enviar/i }),
    ).toBeDisabled();

    fireEvent.change(input, { target: { value: "ENVIAR" } });
    screen.getByRole("button", { name: /Confirmar y enviar/i }).click();

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/automation/acciones/55/high-confirmar",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ confirmacion: "ENVIAR" }),
        }),
      ),
    );
  });

  it(
    "HIGH approved con next_required_action del backend usa execution_block_reason del API",
    async () => {
      // Contrato T2.1.B (next_required_action API):
      //   Cuando el backend ya manda next_required_action y
      //   execution_block_reason, la UI debe respetarlos · debe mostrar
      //   el motivo literal que viene del backend (no hardcodear texto)
      //   y debe seguir bloqueando el botón "Ejecutar".
      const motivoBackend =
        "MOTIVO_BACKEND_DEDICADO · preview, costo y riesgo antes de efecto externo real.";
      const accion = {
        id: 99,
        opportunity_id: "opp_99",
        playbook_id: "whatsapp_outbound",
        tipo_accion: "enviar_mensaje_whatsapp",
        titulo: "Acción HIGH con contrato API",
        descripcion: "Verifica que la UI use los campos del backend.",
        razon_recomendacion: "",
        estado: "approved",
        riesgo: "high",
        costo_creditos_estimado: 5,
        requires_approval: true,
        result_json: "{}",
        error_message: "",
        created_at: "2026-05-24T00:00:00Z",
        updated_at: "2026-05-24T00:00:00Z",
        approved_at: "2026-05-24T00:00:01Z",
        rejected_at: null,
        completed_at: null,
        next_required_action: "dedicated_confirmation_required",
        execution_block_reason: motivoBackend,
      };
      mockFetchOnce(
        new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
          status: 200,
        }),
      );
      render(<SeccionActionCenter />);
      await waitFor(() =>
        expect(
          screen.getByText(/Acción HIGH con contrato API/),
        ).toBeInTheDocument(),
      );
      // El texto del bloqueo debe venir literal del backend, no del hardcode
      // de la UI · si lo cambia el backend, la UI debe reflejarlo sin tocar
      // código del componente.
      expect(
        screen.getByText(/MOTIVO_BACKEND_DEDICADO/i),
      ).toBeInTheDocument();
      // Sigue sin ofrecer el botón "Ejecutar" en este control genérico
      expect(
        screen.queryByRole("button", { name: /Ejecutar \(dry-run\)/i }),
      ).not.toBeInTheDocument();
      // Botón dedicado del próximo paso sigue presente
      expect(
        screen.getByRole("button", { name: /Confirmar envío HIGH/i }),
      ).toBeInTheDocument();
    },
  );

  it(
    "HIGH approved legacy (sin next_required_action en payload) cae a fallback local",
    async () => {
      // Backwards compat: payloads de versiones previas (sin
      // next_required_action ni execution_block_reason) deben seguir
      // funcionando · la UI calcula localmente y muestra su copy
      // por defecto.
      const accion = {
        id: 100,
        opportunity_id: "opp_100",
        playbook_id: "whatsapp_outbound",
        tipo_accion: "enviar_mensaje_whatsapp",
        titulo: "Acción HIGH legacy",
        descripcion: "Payload sin campos del contrato nuevo",
        razon_recomendacion: "",
        estado: "approved",
        riesgo: "high",
        costo_creditos_estimado: 5,
        requires_approval: true,
        result_json: "{}",
        error_message: "",
        created_at: "2026-05-24T00:00:00Z",
        updated_at: "2026-05-24T00:00:00Z",
        approved_at: "2026-05-24T00:00:01Z",
        rejected_at: null,
        completed_at: null,
      };
      mockFetchOnce(
        new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
          status: 200,
        }),
      );
      render(<SeccionActionCenter />);
      await waitFor(() =>
        expect(screen.getByText(/Acción HIGH legacy/)).toBeInTheDocument(),
      );
      // Copy hardcoded local sigue apareciendo cuando el backend no
      // manda execution_block_reason
      expect(
        screen.getByText(/necesita\s+confirmación dedicada/i),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Ejecutar \(dry-run\)/i }),
      ).not.toBeInTheDocument();
    },
  );

  it(
    "MEDIUM pending legacy (sin contrato API) NO muestra Ejecutar ni Aprobar/Rechazar",
    async () => {
      // Defensivo · MEDIUM se crea en needs_approval, así que un payload
      // con estado=pending y riesgo=medium solo aparece por datos legacy
      // o un bug. Tampoco se puede aprobar desde pending: la matriz
      // TRANSICIONES en permissions.py sólo permite pending →
      // running/cancelled/rejected (nunca pending → approved). Por eso
      // el fallback local del componente NO debe abrir Ejecutar ni
      // ofrecer Aprobar/Rechazar · el control genérico simplemente no
      // tiene una acción válida sobre esta combinación legacy.
      const accion = {
        id: 77,
        opportunity_id: "opp_77",
        playbook_id: "preparar_msg",
        tipo_accion: "preparar_mensaje_whatsapp",
        titulo: "Borrador legacy medium",
        descripcion: "Payload sin next_required_action del backend",
        razon_recomendacion: "",
        estado: "pending",
        riesgo: "medium",
        costo_creditos_estimado: 3,
        requires_approval: true,
        result_json: "{}",
        error_message: "",
        created_at: "2026-05-24T00:00:00Z",
        updated_at: "2026-05-24T00:00:00Z",
        approved_at: null,
        rejected_at: null,
        completed_at: null,
      };
      mockFetchOnce(
        new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
          status: 200,
        }),
      );
      render(<SeccionActionCenter />);
      await waitFor(() =>
        expect(screen.getByText(/Borrador legacy medium/)).toBeInTheDocument(),
      );
      // NO ofrece Ejecutar
      expect(
        screen.queryByRole("button", { name: /Ejecutar \(dry-run\)/i }),
      ).not.toBeInTheDocument();
      // Tampoco ofrece el flujo de aprobación · pending → approved no es
      // transición válida en el backend, así que el control genérico no
      // muestra Aprobar/Rechazar para esta combinación.
      expect(
        screen.queryByRole("button", { name: /^Aprobar$/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Rechazar/i }),
      ).not.toBeInTheDocument();
    },
  );

  it(
    "CRITICAL con next_required_action del backend usa execution_block_reason del API",
    async () => {
      const motivoBackend = "MOTIVO_API_CRITICAL · bloqueo reforzado desde backend.";
      const accion = {
        id: 101,
        opportunity_id: "opp_101",
        playbook_id: "critical_pb",
        tipo_accion: "envio_masivo_clientes",
        titulo: "Acción CRITICAL con contrato API",
        descripcion: "Verifica que la UI use el motivo critical del backend.",
        razon_recomendacion: "",
        estado: "needs_approval",
        riesgo: "critical",
        costo_creditos_estimado: 50,
        requires_approval: true,
        result_json: "{}",
        error_message: "",
        created_at: "2026-05-24T00:00:00Z",
        updated_at: "2026-05-24T00:00:00Z",
        approved_at: null,
        rejected_at: null,
        completed_at: null,
        next_required_action: "reinforced_approval_required",
        execution_block_reason: motivoBackend,
      };
      mockFetchOnce(
        new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
          status: 200,
        }),
      );
      render(<SeccionActionCenter />);
      await waitFor(() =>
        expect(
          screen.getByText(/Acción CRITICAL con contrato API/),
        ).toBeInTheDocument(),
      );
      expect(screen.getByText(/MOTIVO_API_CRITICAL/i)).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Ejecutar \(dry-run\)/i }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /^Aprobar$/i }),
      ).not.toBeInTheDocument();
    },
  );

  it("renderiza acción CRITICAL needs_approval con aviso de bloqueo", async () => {
    const accion = {
      id: 2,
      opportunity_id: "",
      playbook_id: "",
      tipo_accion: "envio_masivo_clientes",
      titulo: "Envío masivo prueba",
      descripcion: "Manda mensajes a todos",
      razon_recomendacion: "",
      estado: "needs_approval",
      riesgo: "critical",
      costo_creditos_estimado: 100,
      requires_approval: true,
      result_json: "{}",
      error_message: "",
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T00:00:00Z",
      approved_at: null,
      rejected_at: null,
      completed_at: null,
    };
    mockFetchOnce(
      new Response(JSON.stringify({ acciones: [accion], count: 1 }), {
        status: 200,
      }),
    );
    render(<SeccionActionCenter />);
    await waitFor(() =>
      expect(screen.getByText(/Envío masivo prueba/)).toBeInTheDocument(),
    );
    // Aviso de CRITICAL bloqueada
    expect(
      screen.getByText(/Esta acción es crítica/i),
    ).toBeInTheDocument();
    // Crítico NO ofrece "Aprobar" en T2.1.B
    expect(
      screen.queryByRole("button", { name: /^Aprobar$/i }),
    ).not.toBeInTheDocument();
  });
});
