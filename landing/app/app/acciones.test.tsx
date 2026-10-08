// landing/app/app/acciones.test.tsx — Server actions del piloto app-first.
//
// La identidad sale SIEMPRE de la sesión del servidor: un usuario_id o
// workspace_id metido en el formulario se ignora. Sin sesión, ninguna
// acción toca el backend.

import { beforeEach, describe, expect, it, vi } from "vitest";

const llamarApp = vi.fn();
const sesionApp = vi.fn();
const signIn = vi.fn();
const revalidatePath = vi.fn();

class AuthError extends Error {}

vi.mock("@/lib/app-bridge", () => ({ llamarApp }));
vi.mock("@/lib/app-sesion", () => ({
  sesionApp,
  identidad: (s: { usuarioId: number; workspaceId: number }) => ({
    usuario_id: s.usuarioId,
    workspace_id: s.workspaceId,
  }),
}));
vi.mock("@/auth", () => ({ signIn, signOut: vi.fn() }));
vi.mock("next-auth", () => ({ AuthError }));
vi.mock("next/cache", () => ({ revalidatePath }));

const acciones = await import("./acciones");

function form(campos: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(campos)) fd.set(k, v);
  return fd;
}

beforeEach(() => {
  llamarApp.mockReset().mockResolvedValue({ ok: true, data: {} });
  sesionApp.mockReset().mockResolvedValue({ usuarioId: 3, workspaceId: 9, email: "ana@example.com" });
  signIn.mockReset();
  revalidatePath.mockReset();
  vi.stubEnv("DONA_APP_PILOTO_ENABLED", "true");
});

describe("acciones de trabajo", () => {
  it("sin sesión no llaman al backend", async () => {
    sesionApp.mockResolvedValue(null);
    const res = await acciones.crearArea({}, form({ nombre: "Ventas" }));
    expect(res.error).toMatch(/sesión/i);
    expect(llamarApp).not.toHaveBeenCalled();
  });

  it("ignoran la identidad que venga en el formulario", async () => {
    await acciones.crearArea({}, form({ nombre: "Ventas", usuario_id: "1", workspace_id: "1" }));
    expect(llamarApp).toHaveBeenCalledWith("area.crear", {
      usuario_id: 3,
      workspace_id: 9,
      nombre: "Ventas",
      descripcion: "",
    });
    expect(revalidatePath).toHaveBeenCalledWith("/app", "layout");
  });

  it("crearProyecto parte los criterios por línea y exige al menos uno", async () => {
    const vacio = await acciones.crearProyecto(
      {},
      form({ area_id: "2", nombre: "Lanzamiento", objetivo: "Vender", criterios: " \n " }),
    );
    expect(vacio.error).toMatch(/criterio/);
    expect(llamarApp).not.toHaveBeenCalled();

    await acciones.crearProyecto(
      {},
      form({ area_id: "2", nombre: "Lanzamiento", objetivo: "Vender", criterios: "Uno\n\n Dos \n" }),
    );
    expect(llamarApp).toHaveBeenCalledWith("proyecto.crear", expect.objectContaining({
      area_id: 2,
      criterios_aceptacion: ["Uno", "Dos"],
    }));
  });

  it("valida ids numéricos antes de llamar", async () => {
    const res = await acciones.crearTarea({}, form({ proyecto_id: "1 OR 1=1", titulo: "x" }));
    expect(res.error).toBe("Falta el proyecto.");
    expect(llamarApp).not.toHaveBeenCalled();
  });

  it("crearTarea sin agente no envía agente_id", async () => {
    await acciones.crearTarea({}, form({ proyecto_id: "4", titulo: "Borrador", agente_id: "" }));
    const payload = llamarApp.mock.calls[0][1];
    expect(payload).not.toHaveProperty("agente_id");
  });

  it("accionTarea solo admite ejecutar, cancelar y reintentar", async () => {
    expect((await acciones.accionTarea({}, form({ tarea_id: "5", operacion: "borrar" }))).error).toBe(
      "Acción desconocida.",
    );
    await acciones.accionTarea({}, form({ tarea_id: "5", operacion: "reintentar" }));
    expect(llamarApp).toHaveBeenCalledWith("tarea.reintentar", expect.objectContaining({ tarea_id: 5 }));
  });

  it("decidirAprobacion convierte la decisión a booleano", async () => {
    await acciones.decidirAprobacion({}, form({ aprobacion_id: "8", decision: "rechazar" }));
    expect(llamarApp).toHaveBeenCalledWith("aprobacion.decidir", expect.objectContaining({
      aprobacion_id: 8,
      aprobar: false,
    }));
    expect((await acciones.decidirAprobacion({}, form({ aprobacion_id: "8", decision: "sí" }))).error)
      .toBe("Decisión inválida.");
  });

  it("muestra el error de dominio del backend", async () => {
    llamarApp.mockResolvedValue({ ok: false, status: 403, error: "sin_permiso", detalle: "solo owner/admin crean áreas" });
    expect((await acciones.crearArea({}, form({ nombre: "X" }))).error).toBe("Solo owner/admin crean áreas.");
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});

describe("acceso", () => {
  it("entrar traduce un AuthError a un mensaje sin detalles", async () => {
    signIn.mockRejectedValue(new AuthError("CredentialsSignin"));
    const res = await acciones.entrar({}, form({ email: "ana@example.com", password: "mala" }));
    expect(res.error).toMatch(/No pudiste entrar/);
    expect(signIn).toHaveBeenCalledWith("cuenta", expect.objectContaining({ redirectTo: "/app" }));
  });

  it("entrar deja pasar la redirección de éxito", async () => {
    const redireccion = new Error("NEXT_REDIRECT");
    signIn.mockRejectedValue(redireccion);
    await expect(acciones.entrar({}, form({ email: "a@b.c", password: "x" }))).rejects.toBe(redireccion);
  });

  it("con el piloto apagado no intenta entrar ni registrar", async () => {
    vi.stubEnv("DONA_APP_PILOTO_ENABLED", "false");
    await acciones.entrar({}, form({ email: "a@b.c", password: "x" }));
    await acciones.registrar({}, form({ email: "a@b.c", password: "x".repeat(12), password_confirmacion: "x".repeat(12) }));
    expect(signIn).not.toHaveBeenCalled();
    expect(llamarApp).not.toHaveBeenCalled();
  });

  it("registrar valida contraseña y confirmación antes del backend", async () => {
    expect((await acciones.registrar({}, form({ email: "a@b.c", password: "corta", password_confirmacion: "corta" }))).error)
      .toMatch(/10 caracteres/);
    expect((await acciones.registrar({}, form({ email: "a@b.c", password: "x".repeat(12), password_confirmacion: "y".repeat(12) }))).error)
      .toMatch(/no coinciden/);
    expect(llamarApp).not.toHaveBeenCalled();
  });

  it("registrar sin invitación no inicia sesión", async () => {
    llamarApp.mockResolvedValue({ ok: false, status: 403, error: "registro_solo_por_invitacion" });
    const res = await acciones.registrar(
      {},
      form({ email: "intruso@example.com", password: "x".repeat(12), password_confirmacion: "x".repeat(12) }),
    );
    expect(res.error).toBe("Este correo no tiene invitación al piloto.");
    expect(signIn).not.toHaveBeenCalled();
  });
});
