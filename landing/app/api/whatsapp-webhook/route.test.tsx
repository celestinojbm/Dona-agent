// landing/app/api/whatsapp-webhook/route.test.tsx — WhatsApp retirado.
//
// Antes la ruta reenviaba a Render (ver historial: SEC-WEB-05 cubría qué
// headers se reenviaban). En pausa ya no reenvía nada: 410 sin fetch, ni
// siquiera para la verificación GET de Meta o con una firma HMAC presente.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { GET, POST } from "./route";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("/api/whatsapp-webhook · pausa", () => {
  it("GET (verificación de Meta) → 410 sin fetch", async () => {
    const res = await GET();
    expect(res.status).toBe(410);
    expect(await res.json()).toMatchObject({ error: "dona_en_pausa" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("POST con firma de Meta → 410 sin fetch", async () => {
    const res = await POST();
    expect(res.status).toBe(410);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("ya no contiene la URL fija del backend en Render", () => {
    const fuente = readFileSync(
      join(process.cwd(), "app/api/whatsapp-webhook/route.ts"),
      "utf-8",
    );
    expect(fuente).not.toContain("onrender.com");
    expect(fuente).not.toMatch(/fetch\(/);
  });
});
