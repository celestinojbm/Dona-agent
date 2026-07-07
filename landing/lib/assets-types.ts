// landing/lib/assets-types.ts — Tipos compartidos de la Galería de Activos
//
// Los usan tanto el bridge (server-only) como la sección del dashboard
// (client). Por eso viven aparte de assets-bridge.ts (que hace
// `import "server-only"`).

/** Tipo de activo generado por Dona. */
export type TipoAsset = "image" | "video" | "audio" | "web" | "doc";

/**
 * Activo tal como lo devuelve el backend en /internal/assets (ya
 * sanitizado · sin telefono, sin key_storage, sin costo interno).
 */
export interface AssetGaleria {
  id: number;
  tipo: TipoAsset;
  /** URL pública del activo · puede ir vacía si el registro no la tiene. */
  url_publica: string;
  prompt: string;
  modelo: string;
  /** ISO 8601 o null si el backend no lo tiene. */
  creado: string | null;
}

export interface AssetsResponse {
  assets: AssetGaleria[];
  count: number;
}

export interface AssetsApiResult {
  ok: boolean;
  status?: number;
  data?: AssetsResponse;
  error?: string;
}
