// landing/lib/app-bridge.test.ts — Bridge firmado a /internal/app.

import crypto from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { llamarApp } from "@/lib/app-bridge";

const SECRETO = "secreto-de-prueba-bridge";
const fetchSpy = vi.fn();
const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

function respuesta(status: number, cuerpo: unknown) {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
  vi.stubEnv("BACKEND_URL", "https://backend.example.com/");
  vi.stubEnv("INTERNAL_BRIDGE_SECRET", SECRETO);
  fetchSpy.mockReset();
  errorSpy.mockClear();
});
afterEach(() => vi.unstubAllEnvs());

describe("llamarApp", () => {
  it("firma exactamente el body que envía y devuelve los datos", async () => {
    fetchSpy.mockResolvedValue(respuesta(200, { workspaces: [] }));
    const res = await llamarApp("workspaces", { usuario_id: 7 });

    expect(res).toEqual({ ok: true, data: { workspaces: [] } });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("https://backend.example.com/internal/app/workspaces");
    const esperado = crypto.createHmac("sha256", SECRETO).update(init.body).digest("hex");
    expect(init.headers["X-Internal-Signature"]).toBe(esperado);
    expect(JSON.parse(init.body)).toEqual({ usuario_id: 7 });
  });

  it("propaga código y detalle de dominio sin inventar", async () => {
    fetchSpy.mockResolvedValue(
      respuesta(409, { error: "conflicto", detalle: "la tarea está completada, no pendiente" }),
    );
    expect(await llamarApp("tarea.ejecutar", { tarea_id: 1 })).toEqual({
      ok: false,
      status: 409,
      error: "conflicto",
      detalle: "la tarea está completada, no pendiente",
    });
  });

  it("un cuerpo no JSON es un error opaco con el status", async () => {
    fetchSpy.mockResolvedValue(new Response("<html>", { status: 502 }));
    expect(await llamarApp("inicio", {})).toEqual({
      ok: false,
      status: 502,
      error: "backend_502",
      detalle: undefined,
    });
  });

  it("nunca escribe el payload (contraseñas) en el log", async () => {
    fetchSpy.mockResolvedValue(respuesta(401, { error: "credenciales_invalidas" }));
    await llamarApp("auth.verificar", { email: "ana@example.com", password: "clave-que-no-se-loguea" });
    const log = errorSpy.mock.calls.flat().join(" ");
    expect(log).toContain("auth.verificar");
    expect(log).not.toContain("clave-que-no-se-loguea");
    expect(log).not.toContain("ana@example.com");
  });

  it("sin configuración no llama a la red", async () => {
    vi.stubEnv("INTERNAL_BRIDGE_SECRET", "");
    expect(await llamarApp("inicio", {})).toEqual({ ok: false, error: "internal_bridge_secret_missing" });
    vi.stubEnv("BACKEND_URL", "");
    expect(await llamarApp("inicio", {})).toEqual({ ok: false, error: "backend_url_missing" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rechaza nombres de acción que alteren la ruta", async () => {
    for (const accion of ["../admin", "tarea/ejecutar", "a.b.c", "Inicio", ""]) {
      expect(await llamarApp(accion, {})).toEqual({ ok: false, error: "accion_invalida" });
    }
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("distingue timeout de fallo de red", async () => {
    fetchSpy.mockRejectedValueOnce(Object.assign(new Error("aborted"), { name: "AbortError" }));
    expect(await llamarApp("inicio", {})).toEqual({ ok: false, error: "timeout" });
    fetchSpy.mockRejectedValueOnce(new Error("ECONNREFUSED"));
    expect(await llamarApp("inicio", {})).toEqual({ ok: false, error: "fetch_failed" });
  });
});
