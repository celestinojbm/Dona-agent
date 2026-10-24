// landing/lib/rate-limit.test.ts — Cupo en memoria del login del panel.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  LOGIN_MAX_DEFAULT,
  LOGIN_VENTANA_SEGUNDOS_DEFAULT,
  USUARIO_PANEL,
  claveCupo,
  configLogin,
  consumirCupo,
  consumirLogin,
  fijarReloj,
  ipDe,
  reiniciarCupos,
} from "./rate-limit";

const ENV_ORIGINAL = { ...process.env };
let ahora = 1_000_000;

beforeEach(() => {
  ahora = 1_000_000;
  fijarReloj(() => ahora);
  reiniciarCupos();
  delete process.env.RATE_LIMIT_LOGIN_MAX;
  delete process.env.RATE_LIMIT_LOGIN_WINDOW_SECONDS;
});

afterEach(() => {
  fijarReloj(null);
  reiniciarCupos();
  process.env = { ...ENV_ORIGINAL };
});

function reqCon(headers: Record<string, string>): Request {
  return new Request("http://test/api/engineering/login", { headers });
}

describe("configLogin", () => {
  it("usa 5 intentos y 15 minutos si no hay env", () => {
    expect(configLogin()).toEqual({
      maximo: LOGIN_MAX_DEFAULT,
      ventanaSegundos: LOGIN_VENTANA_SEGUNDOS_DEFAULT,
    });
    expect(LOGIN_MAX_DEFAULT).toBe(5);
    expect(LOGIN_VENTANA_SEGUNDOS_DEFAULT).toBe(900);
  });

  it("lee enteros del entorno y ignora valores inválidos", () => {
    process.env.RATE_LIMIT_LOGIN_MAX = "2";
    process.env.RATE_LIMIT_LOGIN_WINDOW_SECONDS = "30";
    expect(configLogin()).toEqual({ maximo: 2, ventanaSegundos: 30 });
    process.env.RATE_LIMIT_LOGIN_MAX = "0";
    process.env.RATE_LIMIT_LOGIN_WINDOW_SECONDS = "no";
    expect(configLogin()).toEqual({
      maximo: LOGIN_MAX_DEFAULT,
      ventanaSegundos: LOGIN_VENTANA_SEGUNDOS_DEFAULT,
    });
  });
});

describe("consumirCupo", () => {
  it("bloquea al llegar al máximo y reabre al pasar la ventana", () => {
    const clave = claveCupo("203.0.113.10", "ana");
    for (let i = 0; i < 5; i++) {
      expect(consumirCupo(clave, 5, 900).permitido).toBe(true);
    }
    const lleno = consumirCupo(clave, 5, 900);
    expect(lleno.permitido).toBe(false);
    expect(lleno.retryAfterSegundos).toBe(900);
    ahora += 900 * 1000;
    expect(consumirCupo(clave, 5, 900).permitido).toBe(true);
  });

  it("dos usuarios con la misma IP no comparten cupo", () => {
    const ana = claveCupo("203.0.113.10", "ana");
    const luis = claveCupo("203.0.113.10", "luis");
    expect(consumirCupo(ana, 1, 900).permitido).toBe(true);
    expect(consumirCupo(ana, 1, 900).permitido).toBe(false);
    expect(consumirCupo(luis, 1, 900).permitido).toBe(true);
  });

  it("el usuario del panel es fijo y no sale del token", () => {
    expect(USUARIO_PANEL).toBe("engineering");
    expect(claveCupo("203.0.113.9", USUARIO_PANEL)).toBe(
      claveCupo("203.0.113.9", "  Engineering "),
    );
  });
});

describe("ipDe", () => {
  it("prefiere el header de la plataforma frente a uno que manda el cliente", () => {
    const ip = ipDe(
      reqCon({
        "x-vercel-forwarded-for": "198.51.100.20",
        "x-forwarded-for": "203.0.113.1, 198.51.100.20",
      }),
    );
    expect(ip).toBe("198.51.100.20");
  });

  it("si solo hay X-Forwarded-For usa el último salto", () => {
    expect(ipDe(reqCon({ "x-forwarded-for": "1.2.3.4, 203.0.113.50" }))).toBe(
      "203.0.113.50",
    );
  });

  it("sin headers cae en un balde compartido", () => {
    expect(ipDe(reqCon({}))).toBe("desconocida");
  });
});

describe("consumirLogin", () => {
  it("aplica el default de 5 por IP del principal", () => {
    for (let i = 0; i < 5; i++) expect(consumirLogin("203.0.113.8").permitido).toBe(true);
    expect(consumirLogin("203.0.113.8").permitido).toBe(false);
    expect(consumirLogin("203.0.113.9").permitido).toBe(true);
  });
});
