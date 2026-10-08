import { describe, expect, it, vi, beforeEach } from "vitest";

// Estos tests ejercitan la lógica de la ruta que sigue DETRÁS del bloqueo
// de pausa (se reutilizará al reconstruir la app). Por eso simulan la pausa
// apagada; que la ruta corta en pausa lo cubre app/api/pausa-rutas.test.tsx.
vi.mock("@/lib/pausa", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/pausa")>()),
  DONA_EN_PAUSA: false,
}));
vi.mock("@/auth", () => ({
  auth: vi.fn(),
}));

vi.mock("@/lib/automation-bridge", () => ({
  confirmarHighDedicado: vi.fn(),
}));

import { auth } from "@/auth";
import { confirmarHighDedicado } from "@/lib/automation-bridge";
import { POST } from "./route";

describe("POST high-confirmar route", () => {
  beforeEach(() => {
    vi.mocked(auth).mockReset();
    vi.mocked(confirmarHighDedicado).mockReset();
    vi.mocked(auth).mockResolvedValue({ subscriptionId: "sub_test" } as never);
    vi.mocked(confirmarHighDedicado).mockResolvedValue({
      ok: true,
      data: { accion: {}, ejecucion: { estado_final: "completed" } },
    } as never);
  });

  it("rechaza confirmacion no-string aunque String(valor) sea ENVIAR", async () => {
    const req = new Request("http://test/api/automation/acciones/9/high-confirmar", {
      method: "POST",
      body: JSON.stringify({ confirmacion: ["ENVIAR"] }),
    });

    const res = await POST(req, { params: Promise.resolve({ id: "9" }) });

    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: "confirmacion_invalida" });
    expect(confirmarHighDedicado).not.toHaveBeenCalled();
  });
});
