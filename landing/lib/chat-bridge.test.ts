// landing/lib/chat-bridge.test.ts — Chat web (Fase 1)
//
// Tests del bridge HMAC del chat. Mismo patrón que reportes-bridge.test.ts.
// Verifica, además de lo estándar, los invariantes de SEGURIDAD del chat:
//   - el body firmado NUNCA incluye telefono (anti-IDOR: el backend lo
//     resuelve desde subscription_id);
//   - la firma HMAC se computa sobre el body exacto y apunta a /internal/chat;
//   - el mensaje se propaga (trim) en el body;
//   - 200 retorna data tipada; 404/401/429 retornan ok=false con status;
//   - timeout retorna ok=false con error timeout (el timeout largo del chat).

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import crypto from "node:crypto";

const ORIGINAL_ENV = { ...process.env };

// HMAC-SHA256 esperado sobre el body EXACTO enviado, con el secret del test.
// Recomputarlo (en vez de sólo verificar el formato hex) detecta que se firme
// un body distinto del que se envía (invariante de seguridad del bridge).
function hmacEsperado(bodyStr: string): string {
  return crypto
    .createHmac("sha256", "test-secret-xyz")
    .update(bodyStr, "utf8")
    .digest("hex");
}

beforeEach(() => {
  process.env.BACKEND_URL = "http://backend.test";
  process.env.INTERNAL_BRIDGE_SECRET = "test-secret-xyz";
  vi.resetModules();
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
  vi.restoreAllMocks();
});


describe("chat-bridge · validación de inputs", () => {
  it("sin subscription_id retorna missing_subscription_id (sin red)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("", "hola");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_subscription_id");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("sin mensaje retorna missing_mensaje (sin red)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "   ");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_mensaje");
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});


describe("chat-bridge · env vars faltantes", () => {
  it("sin BACKEND_URL retorna backend_url_missing", async () => {
    delete process.env.BACKEND_URL;
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "hola");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("backend_url_missing");
  });

  it("sin INTERNAL_BRIDGE_SECRET retorna error", async () => {
    delete process.env.INTERNAL_BRIDGE_SECRET;
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "hola");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("internal_bridge_secret_missing");
  });
});


describe("chat-bridge · firma HMAC, URL y body", () => {
  it("envía X-Internal-Signature con HMAC y apunta a /internal/chat", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "hola" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_xyz", "hola dona");
    expect(fetchSpy).toHaveBeenCalled();
    const url = fetchSpy.mock.calls[0][0] as string;
    expect(url).toBe("http://backend.test/internal/chat");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    // Correctitud (no sólo forma): la firma DEBE ser el HMAC del body EXACTO.
    expect(headers["X-Internal-Signature"]).toBe(hmacEsperado(init.body as string));
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("SEGURIDAD · el body NUNCA incluye telefono (anti-IDOR)", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "ok" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_x", "hola");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ subscription_id: "sub_x", mensaje: "hola" });
    expect(body).not.toHaveProperty("telefono");
  });

  it("propaga el mensaje (trim) en el body", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "ok" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_x", "   con espacios   ");
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.mensaje).toBe("con espacios");
  });
});


describe("chat-bridge · respuestas del backend", () => {
  it("status 200 retorna ok=true con data tipada", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ respuesta: "Hola, soy Dona." }), {
        status: 200,
      }),
    );
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "hola");
    expect(r.ok).toBe(true);
    expect(r.data?.respuesta).toBe("Hola, soy Dona.");
  });

  it("status 404 retorna ok=false status=404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("not found", { status: 404 }),
    );
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "hola");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(404);
  });

  it("status 429 (rate limit) retorna ok=false status=429", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("rate limit", { status: 429 }),
    );
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "spam");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(429);
  });

  it("status 401 retorna ok=false status=401", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("unauthorized", { status: 401 }),
    );
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "hola");
    expect(r.ok).toBe(false);
    expect(r.status).toBe(401);
  });
});


describe("chat-bridge · timeout largo (exclusivo del chat)", () => {
  it("un abort del fetch se mapea a error timeout", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => {
      const err = new Error("The operation was aborted");
      err.name = "AbortError";
      return Promise.reject(err);
    });
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "hola");
    expect(r.ok).toBe(false);
    expect(r.error).toBe("timeout");
  });
});


// ── Fase 3 · media (voz/imagen) ────────────────────────────────────────────

describe("chat-bridge · media · validación", () => {
  it("sólo-audio (sin texto) NO es missing_mensaje y llega al backend", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "oí tu nota" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "", { audio_base64: "QUFBQQ==" });
    expect(r.ok).toBe(true);
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("sólo-imagen (sin texto) NO es missing_mensaje y llega al backend", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "vi tu imagen" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "", { imagen_base64: "QUFBQQ==" });
    expect(r.ok).toBe(true);
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("sin texto y sin media (objeto vacío) sigue siendo missing_mensaje (sin red)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { enviarMensajeChat } = await import("./chat-bridge");
    const r = await enviarMensajeChat("sub_x", "  ", {});
    expect(r.ok).toBe(false);
    expect(r.error).toBe("missing_mensaje");
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("chat-bridge · media · body firmado", () => {
  it("incluye audio_base64/audio_mime cuando hay voz", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "ok" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_x", "escucha esto", {
      audio_base64: "QUFBQQ==",
      audio_mime: "audio/webm",
    });
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      subscription_id: "sub_x",
      mensaje: "escucha esto",
      audio_base64: "QUFBQQ==",
      audio_mime: "audio/webm",
    });
    expect(body).not.toHaveProperty("telefono");
  });

  it("incluye imagen_base64/imagen_mime/imagen_caption cuando hay foto", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "ok" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_x", "", {
      imagen_base64: "QkJCQg==",
      imagen_mime: "image/png",
      imagen_caption: "factura",
    });
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      subscription_id: "sub_x",
      imagen_base64: "QkJCQg==",
      imagen_mime: "image/png",
      imagen_caption: "factura",
    });
    // Sin texto ⇒ sin la clave `mensaje` (no se envía vacía).
    expect(body).not.toHaveProperty("mensaje");
  });

  it("NO agrega claves de media cuando no vienen (sólo-texto queda idéntico)", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "ok" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_x", "hola", {
      // objeto de media presente pero SIN base64 alguno
      audio_mime: "audio/webm",
    });
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ subscription_id: "sub_x", mensaje: "hola" });
  });

  it("la firma HMAC cubre el body con media (firma sobre el body exacto)", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ respuesta: "ok" }), { status: 200 }),
      );
    const { enviarMensajeChat } = await import("./chat-bridge");
    await enviarMensajeChat("sub_x", "", { imagen_base64: "QkJCQg==" });
    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    const bodyStr = init.body as string;
    // El body firmado incluye la media...
    expect(JSON.parse(bodyStr)).toMatchObject({ imagen_base64: "QkJCQg==" });
    // ...y la firma es el HMAC de ESE body exacto (no de un body sin media).
    expect(headers["X-Internal-Signature"]).toBe(hmacEsperado(bodyStr));
  });
});
