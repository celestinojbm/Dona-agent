import { describe, expect, it, vi, beforeEach } from "vitest";

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
