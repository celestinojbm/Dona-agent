"use server";
// landing/app/app/acciones.ts — Server actions del piloto app-first (J7.5).
//
// Cada acción: puerta del piloto + sesión "cuenta" → bridge firmado →
// revalidación. La identidad sale de la sesión del servidor; del formulario
// solo se leen los datos de la acción (ids de objetos, textos). El backend
// valida que cada objeto pertenezca al workspace.

import { revalidatePath } from "next/cache";
import { AuthError } from "next-auth";
import { signIn, signOut } from "@/auth";
import { llamarApp } from "@/lib/app-bridge";
import { appPilotoHabilitado } from "@/lib/app-piloto";
import { identidad, sesionApp } from "@/lib/app-sesion";
import { mensajeError, type EstadoAccion } from "@/lib/app-types";

const ERROR_ENTRAR =
  "No pudiste entrar. Revisa correo y contraseña; tras varios intentos fallidos el acceso se bloquea unos minutos.";

function texto(fd: FormData, campo: string): string {
  const v = fd.get(campo);
  return typeof v === "string" ? v.trim() : "";
}

function entero(fd: FormData, campo: string): number | null {
  const v = texto(fd, campo);
  if (!/^\d{1,12}$/.test(v)) return null;
  const n = Number(v);
  return n > 0 ? n : null;
}

async function ejecutarAccion(
  accion: string,
  datos: Record<string, unknown>,
): Promise<EstadoAccion> {
  const sesion = await sesionApp();
  if (!sesion) return { error: mensajeError("sesion_expirada") };
  const res = await llamarApp(accion, { ...identidad(sesion), ...datos });
  if (!res.ok) return { error: mensajeError(res.error, res.detalle) };
  revalidatePath("/app", "layout");
  return { ok: true };
}

function faltan(...campos: [string, unknown][]): EstadoAccion | null {
  const falta = campos.find(([, v]) => v === null || v === "");
  return falta ? { error: `Falta ${falta[0]}.` } : null;
}

// ── Acceso ──────────────────────────────────────────────────────────────

export async function entrar(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  if (!appPilotoHabilitado()) return { error: ERROR_ENTRAR };
  try {
    await signIn("cuenta", {
      email: texto(fd, "email"),
      password: fd.get("password"),
      redirectTo: "/app",
    });
  } catch (err) {
    if (err instanceof AuthError) return { error: ERROR_ENTRAR };
    throw err; // la redirección de éxito viaja como excepción de Next
  }
  return { ok: true };
}

export async function registrar(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  if (!appPilotoHabilitado()) return { error: mensajeError("registro_solo_por_invitacion") };
  const email = texto(fd, "email");
  const password = fd.get("password");
  if (typeof password !== "string" || password.length < 10) {
    return { error: "La contraseña debe tener al menos 10 caracteres." };
  }
  if (password !== fd.get("password_confirmacion")) {
    return { error: "Las contraseñas no coinciden." };
  }
  const res = await llamarApp("auth.registro", {
    email,
    password,
    nombre: texto(fd, "nombre"),
    nombre_workspace: texto(fd, "nombre_workspace"),
  });
  if (!res.ok) return { error: mensajeError(res.error, res.detalle) };
  try {
    await signIn("cuenta", { email, password, redirectTo: "/app" });
  } catch (err) {
    if (err instanceof AuthError) return { error: ERROR_ENTRAR };
    throw err;
  }
  return { ok: true };
}

export async function salir(): Promise<void> {
  await signOut({ redirectTo: "/app/entrar" });
}

// ── Trabajo ─────────────────────────────────────────────────────────────

export async function crearArea(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  const nombre = texto(fd, "nombre");
  return faltan(["el nombre", nombre]) ??
    ejecutarAccion("area.crear", { nombre, descripcion: texto(fd, "descripcion") });
}

export async function crearProyecto(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  const areaId = entero(fd, "area_id");
  const nombre = texto(fd, "nombre");
  const objetivo = texto(fd, "objetivo");
  const criterios = texto(fd, "criterios")
    .split("\n")
    .map((c) => c.trim())
    .filter(Boolean);
  return (
    faltan(["el área", areaId], ["el nombre", nombre], ["el objetivo", objetivo]) ??
    (criterios.length === 0
      ? { error: "Escribe al menos un criterio de aceptación (uno por línea)." }
      : ejecutarAccion("proyecto.crear", {
          area_id: areaId,
          nombre,
          objetivo,
          criterios_aceptacion: criterios,
        }))
  );
}

export async function crearTarea(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  const proyectoId = entero(fd, "proyecto_id");
  const titulo = texto(fd, "titulo");
  const agenteId = entero(fd, "agente_id");
  return faltan(["el proyecto", proyectoId], ["el título", titulo]) ??
    ejecutarAccion("tarea.crear", {
      proyecto_id: proyectoId,
      titulo,
      descripcion: texto(fd, "descripcion"),
      ...(agenteId ? { agente_id: agenteId } : {}),
    });
}

export async function agregarMensaje(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  const proyectoId = entero(fd, "proyecto_id");
  const contenido = texto(fd, "contenido");
  const tareaId = entero(fd, "tarea_id");
  return faltan(["el proyecto", proyectoId], ["el mensaje", contenido]) ??
    ejecutarAccion("mensaje.crear", {
      proyecto_id: proyectoId,
      contenido,
      ...(tareaId ? { tarea_id: tareaId } : {}),
    });
}

const ACCIONES_TAREA = {
  ejecutar: "tarea.ejecutar",
  cancelar: "tarea.cancelar",
  reintentar: "tarea.reintentar",
} as const;

export async function accionTarea(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  const tareaId = entero(fd, "tarea_id");
  const operacion = texto(fd, "operacion") as keyof typeof ACCIONES_TAREA;
  if (!(operacion in ACCIONES_TAREA)) return { error: "Acción desconocida." };
  return faltan(["la tarea", tareaId]) ??
    ejecutarAccion(ACCIONES_TAREA[operacion], { tarea_id: tareaId });
}

export async function decidirAprobacion(_prev: EstadoAccion, fd: FormData): Promise<EstadoAccion> {
  const aprobacionId = entero(fd, "aprobacion_id");
  const decision = texto(fd, "decision");
  if (decision !== "aprobar" && decision !== "rechazar") return { error: "Decisión inválida." };
  return faltan(["la aprobación", aprobacionId]) ??
    ejecutarAccion("aprobacion.decidir", {
      aprobacion_id: aprobacionId,
      aprobar: decision === "aprobar",
    });
}
