// landing/lib/dashboard-types.ts
// Tipos del response /api/dashboard-data y de las funciones del bridge.
//
// Vive separado de internal-bridge.ts para que los Client Components puedan
// importarlos: internal-bridge.ts tiene `import "server-only"` (T1.4.D
// follow-up) y no puede ser referenciado desde el browser, ni siquiera por
// type-only imports en algunos bundlers de Next.

/** Forma de la transacción tal como la devuelve el backend. */
export type TransaccionResumen = {
  delta: number;
  razon: string;
  saldo_resultante: number;
  creado: string | null;
};

/** Estructura completa del response 200 de /internal/usuario-resumen,
 * y por extensión del JSON que /api/dashboard-data sirve al cliente
 * (después del merge con Stripe overrides + email de sesión). */
export type UsuarioResumen = {
  usuario: {
    id: string;
    email: string | null;
    telefono: string;
  };
  creditos: {
    saldo_actual: number;
    creditos_mensuales: number;
    ultimo_movimiento: TransaccionResumen | null;
  };
  suscripcion: {
    estado: string;
    plan: string;
    stripe_customer_id: string;
    stripe_subscription_id: string;
    current_period_end: number | null;
    cancel_at_period_end: boolean;
    actualizado: string | null;
  };
  transacciones_recientes: TransaccionResumen[];
  resumen: {
    puede_cancelar: boolean;
    dashboard_ready: boolean;
  };
};

export type FetchUsuarioResumenResult =
  | { ok: true; data: UsuarioResumen }
  | { ok: false; status?: number; error: string };
