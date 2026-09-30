// landing/app/api/automation/acciones/[id]/route.test.tsx
//
// Contrato de la lectura canónica GET /api/automation/acciones/:id:
// sesión y suscripción salen de auth(), nunca del navegador; ids y
// cursores se validan estrictamente; los errores del backend se traducen
// al vocabulario de las rutas de acciones.

import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/auth", () => ({
  auth: vi.fn(),
}));

vi.mock("@/lib/automation-bridge", () => ({
  fetchDetalleAccion: vi.fn(),
}));

import { auth } from "@/auth";
import { fetchDetalleAccion } from "@/lib/automation-bridge";
import { GET } from "./route";

function detalle(id = 9) {
  return {
    accion: { id, titulo: "Plan", estado: "needs_approval" },
    eventos: [{ id: 3, evento: "action_created", created_at: "2026-05-09T00:00:00Z" }],
    eventos_hay_mas: false,
    eventos_siguiente_cursor: null,
    eventos_limite: 20,
    leido_en: "2026-05-09T02:00:00Z",
  };
}

function llamar(id: string, query = "") {
  const req = new Request(`http://test/api/automation/acciones/${id}${query}`);
  return GET(req, { params: Promise.resolve({ id }) });
}

describe("GET /api/automation/acciones/:id", () => {
  beforeEach(() => {
    vi.mocked(auth).mockReset();
    vi.mocked(fetchDetalleAccion).mockReset();
    vi.mocked(auth).mockResolvedValue({ subscriptionId: "sub_sesion" } as never);
    vi.mocked(fetchDetalleAccion).mockResolvedValue({ ok: true, data: detalle() } as never);
  });

  it("devuelve la acción de la suscripción de la sesión, sin caché", async () => {
    const res = await llamar("9");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect(await res.json()).toEqual(detalle());
    expect(fetchDetalleAccion).toHaveBeenCalledWith("sub_sesion", 9, {
      antesDe: undefined,
      limite: undefined,
    });
  });

  it("ignora cualquier subscriptionId enviado por el navegador", async () => {
    await llamar("9", "?subscriptionId=sub_ajena&subscription_id=sub_ajena");
    expect(fetchDetalleAccion).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetchDetalleAccion).mock.calls[0][0]).toBe("sub_sesion");
  });

  it("pasa cursor y límite de eventos validados", async () => {
    await llamar("9", "?eventos_antes_de=40&eventos_limite=10");
    expect(fetchDetalleAccion).toHaveBeenCalledWith("sub_sesion", 9, {
      antesDe: 40,
      limite: 10,
    });
  });

  it("401 sin sesión y 403 sin suscripción, sin llamar al backend", async () => {
    vi.mocked(auth).mockResolvedValueOnce(null as never);
    const sinSesion = await llamar("9");
    expect(sinSesion.status).toBe(401);
    expect(await sinSesion.json()).toEqual({ error: "unauthenticated" });

    vi.mocked(auth).mockResolvedValueOnce({} as never);
    const sinSub = await llamar("9");
    expect(sinSub.status).toBe(403);
    expect(await sinSub.json()).toEqual({ error: "no_subscription_in_session" });
    expect(fetchDetalleAccion).not.toHaveBeenCalled();
  });

  it.each(["abc", "0", "-1", "12abc", "1.5", "9999999999999"])(
    "400 invalid_accion_id para id %s",
    async (id) => {
      const res = await llamar(id);
      expect(res.status).toBe(400);
      expect(await res.json()).toEqual({ error: "invalid_accion_id" });
      expect(fetchDetalleAccion).not.toHaveBeenCalled();
    },
  );

  it("400 con cursor o límite inválidos", async () => {
    const cursor = await llamar("9", "?eventos_antes_de=x");
    expect(await cursor.json()).toEqual({ error: "invalid_eventos_cursor" });
    const limite = await llamar("9", "?eventos_limite=51");
    expect(await limite.json()).toEqual({ error: "invalid_eventos_limite" });
    const cero = await llamar("9", "?eventos_limite=0");
    expect(cero.status).toBe(400);
    expect(fetchDetalleAccion).not.toHaveBeenCalled();
  });

  it("404 accion_not_found cuando la acción es ajena o no existe", async () => {
    vi.mocked(fetchDetalleAccion).mockResolvedValueOnce({
      ok: false,
      status: 404,
      error: "backend_404",
    } as never);
    const res = await llamar("9");
    expect(res.status).toBe(404);
    expect(await res.json()).toEqual({ error: "accion_not_found" });
  });

  it("504 en timeout y 502 en cualquier otro fallo del backend", async () => {
    vi.mocked(fetchDetalleAccion).mockResolvedValueOnce({
      ok: false,
      error: "timeout",
    } as never);
    const timeout = await llamar("9");
    expect(timeout.status).toBe(504);
    expect(await timeout.json()).toEqual({ error: "backend_timeout" });

    for (const fallo of [
      { ok: false, status: 500, error: "backend_500" },
      { ok: false, status: 401, error: "backend_401" },
      { ok: false, error: "fetch_failed" },
      { ok: false, error: "backend_url_missing" },
    ]) {
      vi.mocked(fetchDetalleAccion).mockResolvedValueOnce(fallo as never);
      const res = await llamar("9");
      expect(res.status).toBe(502);
      expect(await res.json()).toEqual({ error: "backend_unavailable" });
    }
  });

  it("502 si el backend devuelve una acción con otro id", async () => {
    vi.mocked(fetchDetalleAccion).mockResolvedValueOnce({
      ok: true,
      data: detalle(10),
    } as never);
    const res = await llamar("9");
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({ error: "backend_unavailable" });
  });
});
