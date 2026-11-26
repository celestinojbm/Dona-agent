// landing/lib/ortografia.test.ts — Guardia de ortografía de la interfaz.
//
// Recorre los textos visibles (literales con espacios y texto JSX) de
// app/, components/ y lib/ y falla si aparece una palabra que en español
// siempre lleva tilde o eñe ("sesion", "Contrasena", "numero"...), o un
// anglicismo que ya se sustituyó en la interfaz ("dashboard", "emails").
//
// No mira comentarios, imports ni identificadores: `creditos` como clave
// de objeto es válido; "Tus creditos" como texto no.

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SIN_TILDE = [
  "sesion", "contrasena", "contrasenas", "suscripcion", "numero", "numeros",
  "credito", "creditos", "politica", "estatico", "estatica", "orquestacion",
  "bitacora", "proximo", "proxima", "proximos", "proximas", "informacion",
  "configuracion", "conexion", "telefono", "pagina", "aqui", "tambien",
  "facil", "rapido", "rapida", "ultimo", "ultima", "ultimos", "codigo",
  "metodo", "analisis", "automatico", "automatica", "despues", "todavia",
  "anadir", "espanol", "diseno", "disenos", "pequeno", "pequena", "tamano",
  "revision", "exito", "electronico", "notificacion", "operacion",
  "transaccion", "descripcion", "opcion", "seccion", "direccion", "razon",
  "aprobacion", "ejecucion", "integracion", "autenticacion", "verificacion",
  "cancelacion", "facturacion", "escribenos", "intentalo", "cuentale",
  "pidele", "escribele", "ademas", "segun", "minimo", "maximo", "categoria",
  "categorias", "catalogo", "movil", "unico", "unica", "metrica", "metricas",
  "limite", "limites", "vacio", "vacia", "campana", "creacion", "generacion",
  "conversacion", "olvidaste", "podras", "veras", "sera", "seran", "podra",
];

const ANGLICISMOS = ["dashboard", "emails", "outputs"];

const PALABRAS = new RegExp(
  `(?<![\\w\\-/.@#])(${[...SIN_TILDE, ...ANGLICISMOS].join("|")})(?![\\w\\-/.@])`,
  "i",
);

// Literales "…", '…', `…` y texto JSX >…<.
const TEXTOS = /"([^"\\\n]{2,})"|'([^'\\\n]{2,})'|`([^`]{2,})`|>([^<>{}\n]{2,})</g;

function archivosFuente(dir: string): string[] {
  const salida: string[] = [];
  for (const nombre of readdirSync(dir)) {
    if (nombre === "node_modules" || nombre.startsWith(".")) continue;
    const ruta = join(dir, nombre);
    if (statSync(ruta).isDirectory()) salida.push(...archivosFuente(ruta));
    else if (/\.(ts|tsx)$/.test(nombre) && !/\.test\./.test(nombre)) salida.push(ruta);
  }
  return salida;
}

describe("Ortografía de la interfaz", () => {
  it("ningún texto visible pierde tildes/eñes ni usa anglicismos retirados", () => {
    const hallazgos: string[] = [];
    for (const ruta of ["app", "components", "lib"].flatMap(archivosFuente)) {
      // Rutas de API que solo registran en servidor (logs) quedan fuera.
      if (ruta.includes(`${join("app", "api")}`)) continue;
      readFileSync(ruta, "utf-8")
        .split("\n")
        .forEach((linea, i) => {
          const limpia = linea.trim();
          if (/^(\/\/|\*|\/\*|\{\/\*|import )/.test(limpia)) return;
          if (/console\.|fetch\(/.test(linea)) return;
          // Texto JSX en su propia línea (sin símbolos de código).
          // Las claves de objeto (`creditos: 100,`) no son texto visible.
          const lineaDeTexto =
            /^[A-Za-zÁÉÍÓÚÑáéíóúñ¿¡][^<>{}=;()"'`]*$/.test(limpia) &&
            !/^[\w$]+\??:\s/.test(limpia)
            ? [limpia]
            : [];
          const textos = [
            ...lineaDeTexto,
            ...[...linea.matchAll(TEXTOS)].map((m) => m.slice(1).find(Boolean) ?? ""),
          ];
          // Atributos visibles de una sola palabra (placeholder="Contraseña").
          const atributos = [
            ...linea.matchAll(/(?:placeholder|aria-label|title|label)[=:]\s*["']([^"']+)["']/g),
          ].map((m) => `${m[1]} `);
          for (const texto of [...textos, ...atributos]) {
            if (!texto.includes(" ")) continue; // claves, rutas, ids
            const hit = PALABRAS.exec(texto);
            if (hit) hallazgos.push(`${ruta}:${i + 1} «${hit[1]}» en: ${texto.trim()}`);
          }
        });
    }
    expect(hallazgos).toEqual([]);
  });
});
