// landing/lib/app-types.ts — Tipos de la API interna /internal/app (J7.5).
//
// Espejo de los dicts que devuelve agent/app_first/{repositorio,ejecucion}.py.
// Sin "server-only": los componentes cliente también los usan.

export type EstadoTarea =
  | "pendiente"
  | "en_ejecucion"
  | "necesita_aprobacion"
  | "bloqueada"
  | "completada"
  | "fallida"
  | "cancelada";

export interface Workspace {
  id: number;
  nombre: string;
  rol: "owner" | "admin" | "miembro";
}

export interface Area {
  id: number;
  nombre: string;
  descripcion: string;
}

export interface Proyecto {
  id: number;
  area_id: number;
  nombre: string;
  objetivo: string;
  criterios_aceptacion: string[];
  responsable_usuario_id: number | null;
  estado: "activo" | "archivado";
  creado: string | null;
}

export interface Agente {
  id: number;
  nombre: string;
  rol: "responsable" | "ejecutor";
  instrucciones: string;
  herramientas_permitidas: string[];
  modelo: string;
  presupuesto_max_unidades: number;
}

export interface Tarea {
  id: number;
  proyecto_id: number;
  titulo: string;
  descripcion: string;
  asignada_a_agente_id: number | null;
  estado: EstadoTarea;
  motivo_bloqueo: string | null;
  creado: string | null;
  actualizado: string | null;
}

export interface Ejecucion {
  id: number;
  agente_id: number;
  intento: number;
  estado: string;
  error_codigo: string | null;
  unidades_consumidas: number;
  iniciada: string | null;
  terminada: string | null;
}

export interface Evidencia {
  id: number;
  ejecucion_id: number;
  tipo: "texto" | "archivo" | "enlace" | "registro";
  contenido: string;
  hash_sha256: string;
  creado: string | null;
}

export interface Aprobacion {
  id: number;
  ejecucion_id: number;
  operacion: string;
  riesgo: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  preview: Record<string, unknown>;
  estado: "pendiente" | "aprobada" | "rechazada" | "caducada";
}

export interface Actividad {
  id: number;
  actor_tipo: "usuario" | "agente" | "sistema";
  actor_id: number | null;
  evento: string;
  objeto_tipo: string;
  objeto_id: number | null;
  datos: Record<string, unknown>;
  creado: string | null;
}

export interface MensajeProyecto {
  id: number;
  tarea_id: number | null;
  autor_tipo: "usuario" | "agente" | "sistema";
  autor_id: number | null;
  contenido: string;
  creado: string | null;
}

export interface Inicio {
  areas: Area[];
  proyectos: Proyecto[];
  aprobaciones_pendientes: Aprobacion[];
  actividad: Actividad[];
}

export interface DetalleProyecto {
  proyecto: Proyecto;
  tareas: Tarea[];
  mensajes: MensajeProyecto[];
}

export interface DetalleTarea {
  tarea: Tarea;
  ejecuciones: Ejecucion[];
  evidencias: Evidencia[];
}

/** Resultado de una llamada al backend. `error` es un código, nunca una traza. */
export type ResultadoApp<T> =
  | { ok: true; data: T }
  | { ok: false; status?: number; error: string; detalle?: string };

/** Estado que devuelven las server actions a sus formularios. */
export interface EstadoAccion {
  error?: string;
  ok?: boolean;
}

const ETIQUETAS_ESTADO: Record<EstadoTarea, string> = {
  pendiente: "Pendiente",
  en_ejecucion: "En ejecución",
  necesita_aprobacion: "Necesita aprobación",
  bloqueada: "Bloqueada",
  completada: "Completada",
  fallida: "Fallida",
  cancelada: "Cancelada",
};

export function etiquetaEstado(estado: string): string {
  return ETIQUETAS_ESTADO[estado as EstadoTarea] ?? estado;
}

const MENSAJES_ERROR: Record<string, string> = {
  registro_solo_por_invitacion: "Este correo no tiene invitación al piloto.",
  credenciales_invalidas: "Correo o contraseña incorrectos.",
  demasiados_intentos: "Demasiados intentos. Espera unos minutos y vuelve a probar.",
  no_encontrado: "No existe o no tienes acceso.",
  sin_permiso: "No tienes permiso para esta acción.",
  conflicto: "La acción choca con el estado actual.",
  valor_invalido: "Algún dato no es válido.",
  timeout: "El backend tardó demasiado. Vuelve a intentarlo.",
  backend_url_missing: "El piloto no está conectado a su backend.",
  internal_bridge_secret_missing: "El piloto no está conectado a su backend.",
  fetch_failed: "No se pudo contactar al backend.",
  sesion_expirada: "Tu sesión terminó. Vuelve a entrar.",
};

/**
 * Mensaje para el usuario. El detalle de dominio (ya en español) gana,
 * salvo en no_encontrado: ahí el detalle es el nombre de la tabla.
 */
export function mensajeError(error: string, detalle?: string): string {
  if (detalle && error !== "no_encontrado") return detalle.charAt(0).toUpperCase() + detalle.slice(1) + ".";
  return MENSAJES_ERROR[error] ?? "No se pudo completar la acción.";
}
