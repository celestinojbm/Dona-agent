// landing/lib/accion-formato.test.ts
//
// Tests puros (sin DOM) de los helpers de presentación del Centro de
// acción. Se prueban los bordes que importan para no inventar datos:
// nulls, JSON inválido y JSON vacío.

import { afterAll, beforeAll, describe, it, expect } from "vitest";
import {
  etiquetaEvento,
  formatearFechaHora,
  formatearFechaHoraSegundos,
  lineaTiempoAccion,
  resumenResultado,
} from "./accion-formato";

describe("formatearFechaHora", () => {
  it("formatea un ISO válido con año y hora", () => {
    const texto = formatearFechaHora("2026-05-09T12:30:00Z");
    expect(texto).toContain("2026");
    expect(texto).toMatch(/\d{2}:\d{2}/);
  });

  it("devuelve cadena vacía para null, undefined, vacío o inválido", () => {
    expect(formatearFechaHora(null)).toBe("");
    expect(formatearFechaHora(undefined)).toBe("");
    expect(formatearFechaHora("")).toBe("");
    expect(formatearFechaHora("no-es-fecha")).toBe("");
  });
});

describe("lineaTiempoAccion", () => {
  it("solo incluye hitos con timestamp real", () => {
    const hitos = lineaTiempoAccion({
      created_at: "2026-05-09T00:00:00Z",
      updated_at: "2026-05-09T01:00:00Z",
      approved_at: null,
      rejected_at: null,
      completed_at: null,
    });
    expect(hitos.map((h) => h.clave)).toEqual(["created_at", "updated_at"]);
    expect(hitos[0].etiqueta).toBe("Creada");
  });

  it("incluye aprobada/completada cuando existen y conserva el orden", () => {
    const hitos = lineaTiempoAccion({
      created_at: "2026-05-09T00:00:00Z",
      approved_at: "2026-05-09T02:00:00Z",
      completed_at: "2026-05-09T03:00:00Z",
      rejected_at: null,
      updated_at: null,
    });
    expect(hitos.map((h) => h.clave)).toEqual([
      "created_at",
      "approved_at",
      "completed_at",
    ]);
  });

  it("devuelve lista vacía si no hay ningún timestamp", () => {
    expect(
      lineaTiempoAccion({
        created_at: null,
        approved_at: null,
        rejected_at: null,
        completed_at: null,
        updated_at: null,
      }),
    ).toEqual([]);
  });
});

describe("resumenResultado", () => {
  it("convierte JSON plano en filas legibles", () => {
    const resumen = resumenResultado(
      JSON.stringify({ canal: "whatsapp", enviados: 3, ok: true }),
    );
    expect(resumen.vacio).toBe(false);
    expect(resumen.filas).toEqual([
      { clave: "canal", valor: "whatsapp" },
      { clave: "enviados", valor: "3" },
      { clave: "ok", valor: "true" },
    ]);
  });

  it("serializa valores anidados en vez de aplanarlos", () => {
    const resumen = resumenResultado(
      JSON.stringify({ detalle: { a: 1 }, lista: [1, 2] }),
    );
    expect(resumen.filas).toEqual([
      { clave: "detalle", valor: '{"a":1}' },
      { clave: "lista", valor: "[1,2]" },
    ]);
  });

  it("marca vacío cuando no hay result_json o el objeto está vacío", () => {
    expect(resumenResultado("").vacio).toBe(true);
    expect(resumenResultado(null).vacio).toBe(true);
    expect(resumenResultado("{}").vacio).toBe(true);
  });

  it("conserva el texto crudo cuando el JSON no es parseable", () => {
    const resumen = resumenResultado("{no-json");
    expect(resumen.vacio).toBe(false);
    expect(resumen.filas).toEqual([]);
    expect(resumen.crudo).toBe("{no-json");
  });
});

describe("fechas del backend sin zona", () => {
  // Huso fijo distinto de UTC: en CI (UTC) el bug no se vería.
  const tzOriginal = process.env.TZ;
  beforeAll(() => {
    process.env.TZ = "America/Los_Angeles";
  });
  afterAll(() => {
    process.env.TZ = tzOriginal;
  });

  it("interpreta un ISO sin zona como UTC, igual que su forma con Z", () => {
    // datetime.utcnow().isoformat() no lleva zona: leerlo como hora local
    // desplazaría la fecha según el huso del navegador.
    expect(formatearFechaHora("2026-05-09T12:30:00")).toBe(
      formatearFechaHora("2026-05-09T12:30:00Z"),
    );
    expect(formatearFechaHora("2026-05-09T12:30:00.123456")).toBe(
      formatearFechaHora("2026-05-09T12:30:00.123Z"),
    );
    expect(formatearFechaHoraSegundos("2026-05-09T12:30:07")).toBe(
      formatearFechaHoraSegundos("2026-05-09T12:30:07Z"),
    );
  });
});

describe("etiquetaEvento", () => {
  it("traduce eventos conocidos y no disfraza los desconocidos", () => {
    expect(etiquetaEvento("action_approved")).toEqual({
      texto: "Acción aprobada",
      conocido: true,
    });
    expect(etiquetaEvento("evento_nuevo_x")).toEqual({
      texto: "Evento registrado",
      conocido: false,
    });
  });
});
