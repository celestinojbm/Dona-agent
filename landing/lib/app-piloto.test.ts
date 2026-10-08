// landing/lib/app-piloto.test.ts — La puerta del piloto solo abre con "true".

import { describe, expect, it } from "vitest";
import { appPilotoHabilitado } from "@/lib/app-piloto";

describe("appPilotoHabilitado", () => {
  it.each([undefined, "", "false", "1", "yes", "TRUE", "on", "true1"])(
    "%s → cerrado",
    (valor) => expect(appPilotoHabilitado(valor)).toBe(false),
  );
  it.each(["true", " true ", "true\n"])("%j → abierto", (valor) =>
    expect(appPilotoHabilitado(valor)).toBe(true),
  );
});
