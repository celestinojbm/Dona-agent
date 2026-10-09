// landing/lib/pausa.ts — Interruptor central de "Dona en pausa".
//
// Dona está retirada de circulación: no acepta suscripciones, compras ni
// acceso al dashboard. Este módulo es la ÚNICA fuente del estado de pausa.
//
// Es una constante en código, NO una variable de entorno: una env vacía o
// mal escrita en Vercel no puede "despausar" la web. Cambiarla exige un PR
// revisado. Aun así, las rutas de cobro ya no tienen código de Stripe (la
// pausa no es un interruptor comercial): reactivar el cobro es un PR de
// relanzamiento aparte, con su propio checklist.
//
// Sin dependencias de servidor: se puede importar desde componentes cliente.

export const DONA_EN_PAUSA = true as const;

export const CODIGO_PAUSA = "dona_en_pausa" as const;

export const MENSAJE_PAUSA =
  "Dona está completo. Todas las plazas están ocupadas y por ahora no aceptamos nuevas suscripciones ni compras.";

/** Cuerpo JSON estándar de las rutas API bloqueadas por la pausa. */
export const CUERPO_PAUSA = {
  error: CODIGO_PAUSA,
  mensaje: MENSAJE_PAUSA,
} as const;
