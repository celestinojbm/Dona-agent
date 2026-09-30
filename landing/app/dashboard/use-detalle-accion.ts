"use client";

// landing/app/dashboard/use-detalle-accion.ts
//
// Lectura canónica de una acción para el panel de detalle:
//   GET /api/automation/acciones/:id  → acción + página de su bitácora
//
// Es la ÚNICA fuente que marca el estado como verificado. La tarjeta de la
// lista solo siembra un snapshot para no abrir el panel en blanco; con ese
// snapshot no se decide nada.
//
// Carreras: cada lectura lleva un número de secuencia. `invalidar()` (al
// empezar una decisión) sube la secuencia, así que una lectura que salió
// ANTES de la decisión y responde después se descarta en vez de marcar
// como verificado un estado previo a la decisión.

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AccionAutomatizacion,
  DetalleAccionResponse,
  EventoAccion,
} from "@/lib/automation-types";
import { mensajeDeErrorAccion } from "@/lib/accion-errores";

export type FaseDetalle =
  /** Hay una lectura en curso (con o sin datos previos en pantalla). */
  | "cargando"
  /** La última lectura canónica respondió y nada la invalidó después. */
  | "verificado"
  /** Hay datos en pantalla, pero no están verificados (falló o se invalidó). */
  | "sin_verificar"
  /** La lectura respondió 404: no existe o no es de esta suscripción. */
  | "ausente"
  /** Falló la lectura y no hay nada que mostrar. */
  | "error";

export interface EstadoDetalle {
  fase: FaseDetalle;
  accion: AccionAutomatizacion | null;
  /** De dónde salen los datos mostrados. */
  origen: "lectura" | "lista" | null;
  /** Momento (UTC, del servidor) de la última lectura canónica exitosa. */
  leidoEn: string | null;
  /** Mensaje de la última lectura fallida · null si no falló. */
  error: string | null;
  /** true cuando hubo al menos una lectura canónica de eventos. */
  eventosCargados: boolean;
  eventos: EventoAccion[];
  eventosCursor: number | null;
  cargandoMasEventos: boolean;
  errorMasEventos: string | null;
}

const VACIO: EstadoDetalle = {
  fase: "cargando",
  accion: null,
  origen: null,
  leidoEn: null,
  error: null,
  eventosCargados: false,
  eventos: [],
  eventosCursor: null,
  cargandoMasEventos: false,
  errorMasEventos: null,
};

const MENSAJE_SIN_CONEXION =
  "No pudimos conectar con el servidor para leer la acción. Revisa tu conexión e intenta de nuevo.";

type Lectura =
  | { ok: true; data: DetalleAccionResponse }
  | { ok: false; status: number; mensaje: string };

async function leer(id: number, antesDe?: number): Promise<Lectura> {
  const qs = antesDe ? `?eventos_antes_de=${antesDe}` : "";
  try {
    const res = await fetch(`/api/automation/acciones/${id}${qs}`, {
      cache: "no-store",
    });
    let cuerpo: unknown = null;
    try {
      cuerpo = await res.json();
    } catch {
      cuerpo = null;
    }
    const data = cuerpo as DetalleAccionResponse | null;
    if (res.ok && data && data.accion?.id === id && Array.isArray(data.eventos)) {
      return { ok: true, data };
    }
    const status = res.ok ? 502 : res.status;
    return { ok: false, status, mensaje: mensajeDeErrorAccion(status, cuerpo) };
  } catch {
    return { ok: false, status: 0, mensaje: MENSAJE_SIN_CONEXION };
  }
}

export interface DetalleAccionApi {
  estado: EstadoDetalle;
  /**
   * Relee la acción. Devuelve la acción verificada, o null si la lectura
   * falló, respondió 404 o quedó invalidada por una decisión posterior.
   */
  recargar: () => Promise<AccionAutomatizacion | null>;
  /** Marca el estado mostrado como no verificado (antes de un POST). */
  invalidar: () => void;
  cargarMasEventos: () => Promise<void>;
}

/**
 * El panel se monta con `key={id}`: una acción distinta es una instancia
 * nueva del hook, así que no hay estado de otra acción que limpiar.
 */
export function useDetalleAccion(
  id: number,
  semilla: AccionAutomatizacion | null,
): DetalleAccionApi {
  const [estado, setEstado] = useState<EstadoDetalle>(() => {
    const snapshot = semilla?.id === id ? semilla : null;
    return { ...VACIO, accion: snapshot, origen: snapshot ? "lista" : null };
  });
  const seq = useRef(0);
  // false tras desmontar · una respuesta tardía no toca estado.
  const montado = useRef(true);
  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  // Aplica una lectura · descarta la respuesta si otra lectura o una
  // decisión empezó después (ya no describe el estado vigente).
  const aplicar = useCallback((r: Lectura, mia: number): AccionAutomatizacion | null => {
    if (!montado.current || mia !== seq.current) return null;
    if (r.ok) {
      setEstado((e) => ({
        ...e,
        fase: "verificado",
        accion: r.data.accion,
        origen: "lectura",
        leidoEn: r.data.leido_en ?? null,
        error: null,
        eventosCargados: true,
        eventos: r.data.eventos,
        eventosCursor: r.data.eventos_hay_mas
          ? r.data.eventos_siguiente_cursor
          : null,
        errorMasEventos: null,
      }));
      return r.data.accion;
    }
    if (r.status === 404) {
      setEstado({ ...VACIO, fase: "ausente", error: r.mensaje });
      return null;
    }
    setEstado((e) => ({
      ...e,
      fase: e.accion ? "sin_verificar" : "error",
      error: r.mensaje,
    }));
    return null;
  }, []);

  const recargar = useCallback(async () => {
    const mia = ++seq.current;
    setEstado((e) => ({ ...e, fase: "cargando", error: null }));
    return aplicar(await leer(id), mia);
  }, [id, aplicar]);

  const invalidar = useCallback(() => {
    seq.current += 1;
    setEstado((e) =>
      e.fase === "verificado" || e.fase === "cargando"
        ? { ...e, fase: e.accion ? "sin_verificar" : "cargando", error: null }
        : e,
    );
  }, []);

  const cursor = estado.eventosCursor;
  const cargarMasEventos = useCallback(async () => {
    if (cursor === null) return;
    setEstado((e) => ({ ...e, cargandoMasEventos: true, errorMasEventos: null }));
    const r = await leer(id, cursor);
    if (!montado.current) return;
    setEstado((e) => {
      if (!r.ok) {
        return { ...e, cargandoMasEventos: false, errorMasEventos: r.mensaje };
      }
      // Solo se toman los eventos: la página no reemplaza el estado de la
      // acción ni su verificación.
      const vistos = new Set(e.eventos.map((ev) => ev.id));
      return {
        ...e,
        cargandoMasEventos: false,
        eventos: [...e.eventos, ...r.data.eventos.filter((ev) => !vistos.has(ev.id))],
        eventosCursor: r.data.eventos_hay_mas ? r.data.eventos_siguiente_cursor : null,
      };
    });
  }, [id, cursor]);

  // Lectura canónica al montar · el estado inicial ya es "cargando".
  useEffect(() => {
    const mia = ++seq.current;
    void (async () => {
      aplicar(await leer(id), mia);
    })();
  }, [id, aplicar]);

  return { estado, recargar, invalidar, cargarMasEventos };
}
