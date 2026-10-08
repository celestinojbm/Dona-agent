// landing/lib/app-types.test.ts — Mensajes de error y etiquetas de estado.

import { describe, expect, it } from "vitest";
import { etiquetaEstado, mensajeError } from "@/lib/app-types";

describe("mensajeError", () => {
  it("usa el detalle de dominio cuando existe", () => {
    expect(mensajeError("valor_invalido", "nombre es obligatorio")).toBe("Nombre es obligatorio.");
  });
  it("no muestra nombres de tabla en no_encontrado", () => {
    expect(mensajeError("no_encontrado", "app_tareas")).toBe("No existe o no tienes acceso.");
  });
  it("cae a un mensaje genérico con códigos desconocidos", () => {
    expect(mensajeError("backend_500")).toBe("No se pudo completar la acción.");
  });
});

describe("etiquetaEstado", () => {
  it("traduce los estados conocidos y deja pasar los demás", () => {
    expect(etiquetaEstado("necesita_aprobacion")).toBe("Necesita aprobación");
    expect(etiquetaEstado("otro")).toBe("otro");
  });
});
