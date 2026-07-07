// landing/lib/reportes-types.ts — Tipos compartidos de Reportes/Medición
//
// Los usan tanto el bridge (server-only) como la sección del dashboard
// (client). Por eso viven aparte de reportes-bridge.ts (que hace
// `import "server-only"`).

/** Período del reporte. */
export type PeriodoReporte = "mes" | "semana";

/** Una categoría de gasto con su total agregado. */
export interface CategoriaGasto {
  categoria: string;
  total: number;
}

/**
 * Comparación de ventas contra el período previo (sólo semana). Null cuando
 * no hay ventas previas contra las que comparar.
 */
export interface ComparacionSemanaPrevia {
  delta_ventas_pct: number;
}

/**
 * Reporte tal como lo devuelve el backend en /internal/reportes (ya
 * sanitizado · sin telefono, sin filas crudas de transacciones).
 *
 * Los campos específicos de semana (pedidos_entregados, pedidos_pendientes,
 * comparacion_semana_previa) sólo vienen cuando periodo === "semana".
 */
export interface Reporte {
  periodo: PeriodoReporte;
  /** Etiqueta legible del período, p.ej. "octubre 2026" o "30/06 → 07/07". */
  etiqueta: string;
  año?: number;
  mes?: number;
  inicio: string;
  fin: string;
  ventas: number;
  gastos: number;
  utilidad: number;
  num_pedidos: number;
  num_transacciones: number;
  pedidos_entregados?: number;
  pedidos_pendientes?: number;
  top_categorias: CategoriaGasto[];
  comparacion_semana_previa?: ComparacionSemanaPrevia | null;
  /** False cuando no hubo transacciones ni pedidos → empty state. */
  hay_datos: boolean;
}

export interface ReportesResponse {
  reporte: Reporte;
}

export interface ReportesApiResult {
  ok: boolean;
  status?: number;
  data?: ReportesResponse;
  error?: string;
}
