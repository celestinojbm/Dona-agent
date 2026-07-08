// landing/app/api/chat/route.test.ts — Fase 3 · media (voz/imagen)
//
// El route acepta texto y/o media, valida caps y formato, y SIEMPRE resuelve
// subscription_id de la sesión server-side (nunca del cliente). Estos tests
// cubren: reenvío de media a la bridge, invariante anti-IDOR, caps de tamaño y
// formato, y el mapeo de errores del backend.

import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/auth", () => ({ auth: vi.fn() }));
vi.mock("@/lib/chat-bridge", () => ({ enviarMensajeChat: vi.fn() }));

import { auth } from "@/auth";
import { enviarMensajeChat } from "@/lib/chat-bridge";
import { POST } from "./route";

function reqCon(body: unknown): Request {
  return new Request("http://test/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  vi.mocked(auth).mockReset();
  vi.mocked(enviarMensajeChat).mockReset();
  vi.mocked(auth).mockResolvedValue({ subscriptionId: "sub_test" } as never);
  vi.mocked(enviarMensajeChat).mockResolvedValue({
    ok: true,
    data: { respuesta: "ok" },
  } as never);
});

describe("POST /api/chat · media reenviada a la bridge", () => {
  it("reenvía imagen (base64 + mime) a la bridge", async () => {
    const res = await POST(
      reqCon({ mensaje: "mira", imagen_base64: "QkJCQg==", imagen_mime: "image/png" }),
    );
    expect(res.status).toBe(200);
    expect(enviarMensajeChat).toHaveBeenCalledWith(
      "sub_test",
      "mira",
      expect.objectContaining({ imagen_base64: "QkJCQg==", imagen_mime: "image/png" }),
    );
  });

  it("reenvía audio (base64 + mime) sin texto", async () => {
    await POST(reqCon({ audio_base64: "QUFBQQ==", audio_mime: "audio/webm" }));
    expect(enviarMensajeChat).toHaveBeenCalledWith(
      "sub_test",
      "",
      expect.objectContaining({ audio_base64: "QUFBQQ==", audio_mime: "audio/webm" }),
    );
  });

  it("texto-solo pasa media=undefined (sin ruido)", async () => {
    await POST(reqCon({ mensaje: "hola" }));
    expect(enviarMensajeChat).toHaveBeenCalledWith("sub_test", "hola", undefined);
  });

  it("descarta un mime que no corresponde al adjunto (defensa)", async () => {
    await POST(reqCon({ audio_base64: "QUFBQQ==", audio_mime: "text/plain" }));
    const media = vi.mocked(enviarMensajeChat).mock.calls[0][2];
    expect(media?.audio_base64).toBe("QUFBQQ==");
    expect(media?.audio_mime).toBeUndefined();
  });
});

describe("POST /api/chat · SEGURIDAD anti-IDOR", () => {
  it("IGNORA subscription_id del cliente y usa el de la sesión", async () => {
    await POST(reqCon({ mensaje: "hola", subscription_id: "sub_ATACANTE" }));
    const [sub] = vi.mocked(enviarMensajeChat).mock.calls[0];
    expect(sub).toBe("sub_test");
    expect(sub).not.toBe("sub_ATACANTE");
  });

  it("IGNORA un telefono inyectado en el body", async () => {
    await POST(reqCon({ mensaje: "hola", telefono: "19998887777" }));
    // La bridge sólo recibe (subscriptionId, mensaje, media) — nunca telefono.
    expect(enviarMensajeChat).toHaveBeenCalledWith("sub_test", "hola", undefined);
  });

  it("sin sesión → 401 y no llama a la bridge", async () => {
    vi.mocked(auth).mockResolvedValue(null as never);
    const res = await POST(reqCon({ mensaje: "hola" }));
    expect(res.status).toBe(401);
    expect(enviarMensajeChat).not.toHaveBeenCalled();
  });
});

describe("POST /api/chat · caps y formato de adjuntos", () => {
  it("base64 con formato inválido → 400 adjunto_invalido (sin bridge)", async () => {
    const res = await POST(reqCon({ imagen_base64: "no-base64!!!" }));
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: "adjunto_invalido" });
    expect(enviarMensajeChat).not.toHaveBeenCalled();
  });

  it("adjunto que excede 12 MB decodificados → 413 (sin bridge)", async () => {
    // base64 canónico cuyos bytes decodificados superan el cap del route.
    const oversized = "A".repeat(16 * 1024 * 1024 + 4);
    const res = await POST(reqCon({ imagen_base64: oversized }));
    expect(res.status).toBe(413);
    expect(await res.json()).toEqual({ error: "adjunto_demasiado_grande" });
    expect(enviarMensajeChat).not.toHaveBeenCalled();
  });

  it("sin texto ni media → 400 mensaje_vacio", async () => {
    const res = await POST(reqCon({}));
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: "mensaje_vacio" });
    expect(enviarMensajeChat).not.toHaveBeenCalled();
  });
});

describe("POST /api/chat · mapeo de errores del backend", () => {
  it("backend 413 → adjunto_demasiado_grande", async () => {
    vi.mocked(enviarMensajeChat).mockResolvedValue({
      ok: false,
      status: 413,
      error: "backend_413",
    } as never);
    const res = await POST(reqCon({ mensaje: "x", imagen_base64: "QkJCQg==" }));
    expect(res.status).toBe(413);
    expect(await res.json()).toEqual({ error: "adjunto_demasiado_grande" });
  });

  it("backend 400 → adjunto_invalido", async () => {
    vi.mocked(enviarMensajeChat).mockResolvedValue({
      ok: false,
      status: 400,
      error: "backend_400",
    } as never);
    const res = await POST(reqCon({ mensaje: "x", imagen_base64: "QkJCQg==" }));
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ error: "adjunto_invalido" });
  });

  it("backend 429 → rate_limit", async () => {
    vi.mocked(enviarMensajeChat).mockResolvedValue({
      ok: false,
      status: 429,
      error: "backend_429",
    } as never);
    const res = await POST(reqCon({ mensaje: "spam" }));
    expect(res.status).toBe(429);
    expect(await res.json()).toEqual({ error: "rate_limit" });
  });
});
