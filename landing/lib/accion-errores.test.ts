// landing/lib/accion-errores.test.ts
//
// Tests del traductor de errores del Centro de acción · cubre los
// códigos que realmente emiten las rutas y los fallbacks por status.

import { describe, it, expect } from "vitest";
import { mensajeDeErrorAccion, MENSAJE_EXITO } from "./accion-errores";

describe("mensajeDeErrorAccion", () => {
  it("traduce los códigos reales de las rutas de acciones", () => {
    expect(mensajeDeErrorAccion(404, { error: "accion_not_found" })).toMatch(
      /ya no existe/i,
    );
    expect(
      mensajeDeErrorAccion(409, { error: "high_confirmation_not_available" }),
    ).toMatch(/ya no admite esta confirmación/i);
    expect(
      mensajeDeErrorAccion(504, { error: "backend_timeout" }),
    ).toMatch(/tardó demasiado/i);
    expect(
      mensajeDeErrorAccion(502, { error: "backend_unavailable" }),
    ).toMatch(/no está disponible/i);
    expect(
      mensajeDeErrorAccion(401, { error: "unauthenticated" }),
    ).toMatch(/sesión expiró/i);
    expect(
      mensajeDeErrorAccion(403, { error: "no_subscription_in_session" }),
    ).toMatch(/suscripción/i);
    expect(
      mensajeDeErrorAccion(400, { error: "confirmacion_invalida" }),
    ).toMatch(/ENVIAR/);
    expect(
      mensajeDeErrorAccion(400, { error: "invalid_accion_id" }),
    ).toMatch(/identificador/i);
  });

  it("cae a un mensaje por defecto cuando el cuerpo no trae código", () => {
    expect(mensajeDeErrorAccion(502, null)).toMatch(/error del servidor/i);
    expect(mensajeDeErrorAccion(500, {})).toMatch(/error del servidor/i);
    expect(mensajeDeErrorAccion(422, { detalle: "x" })).toMatch(
      /estado actual de la acción/i,
    );
  });

  it("ignora códigos desconocidos y usa el fallback por status", () => {
    expect(mensajeDeErrorAccion(418, { error: "codigo_nuevo" })).toMatch(
      /estado actual de la acción/i,
    );
    expect(mensajeDeErrorAccion(503, { error: "codigo_nuevo" })).toMatch(
      /error del servidor/i,
    );
  });

  it("no deja códigos sin mensaje", () => {
    for (const status of [400, 401, 403, 404, 409, 502, 504]) {
      const mensaje = mensajeDeErrorAccion(status, null);
      expect(mensaje.length).toBeGreaterThan(10);
    }
  });
});

describe("MENSAJE_EXITO", () => {
  it("describe cada operación sin prometer efectos externos", () => {
    expect(MENSAJE_EXITO.aprobar).toMatch(/aprobada/i);
    expect(MENSAJE_EXITO.rechazar).toMatch(/historial/i);
    expect(MENSAJE_EXITO.ejecutar).toMatch(/dry-run/i);
  });
});