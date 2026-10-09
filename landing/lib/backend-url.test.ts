// landing/lib/backend-url.test.ts — BACKEND_URL validado (J4).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resolverBackendUrl } from "./backend-url";

let logs: string[];

beforeEach(() => {
  logs = [];
  vi.spyOn(console, "error").mockImplementation((...a: unknown[]) => {
    logs.push(a.map(String).join(" "));
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("resolverBackendUrl", () => {
  it("ausente o vacía → null", () => {
    expect(resolverBackendUrl(undefined)).toBeNull();
    expect(resolverBackendUrl("   ")).toBeNull();
  });

  it("normaliza: sin espacios ni barra final", () => {
    expect(resolverBackendUrl("  https://api.ejemplo.test/  ")).toBe("https://api.ejemplo.test");
    expect(resolverBackendUrl("https://api.ejemplo.test/base//")).toBe("https://api.ejemplo.test/base");
  });

  it.each([
    ["no es URL", "api.ejemplo.test"],
    ["protocolo raro", "ftp://api.ejemplo.test"],
    ["credenciales", "https://usuario:clave@api.ejemplo.test"],
    ["query", "https://api.ejemplo.test/?token=x"],
    ["fragmento", "https://api.ejemplo.test/#x"],
  ])("rechaza %s sin escribir el valor en el log", (_caso, valor) => {
    expect(resolverBackendUrl(valor)).toBeNull();
    expect(logs.join("\n")).not.toContain("ejemplo.test");
    expect(logs.join("\n")).not.toContain("clave");
  });

  it("en producción exige https salvo loopback", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(resolverBackendUrl("http://api.ejemplo.test")).toBeNull();
    expect(resolverBackendUrl("https://api.ejemplo.test")).toBe("https://api.ejemplo.test");
    expect(resolverBackendUrl("http://127.0.0.1:8010")).toBe("http://127.0.0.1:8010");
    expect(resolverBackendUrl("http://localhost:8010")).toBe("http://localhost:8010");
  });

  it("fuera de producción admite http (tests y desarrollo)", () => {
    vi.stubEnv("NODE_ENV", "test");
    expect(resolverBackendUrl("http://backend.test")).toBe("http://backend.test");
  });

  it("lee BACKEND_URL por defecto", () => {
    vi.stubEnv("BACKEND_URL", "https://api.ejemplo.test/");
    expect(resolverBackendUrl()).toBe("https://api.ejemplo.test");
  });
});
