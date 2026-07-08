/**
 * @vitest-environment jsdom
 */
// landing/app/dashboard/seccion-chat.test.tsx
//
// Vista del Chat con Dona. Verifica que el componente:
//   - pinta el turno del usuario y luego la respuesta de Dona (POST /api/chat)
//   - muestra estado "escribiendo…" mientras espera
//   - muestra empty state antes del primer mensaje
//   - muestra una burbuja de error clara ante 4xx/5xx sin tirar la conversación
//   - mapea 429 a un mensaje de "vas muy rápido"

import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  screen,
  waitFor,
  cleanup,
  fireEvent,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import SeccionChat from "./seccion-chat";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function escribirYEnviar(texto: string) {
  const input = screen.getByPlaceholderText("Escríbele a Dona…");
  fireEvent.change(input, { target: { value: texto } });
  const btn = screen.getByLabelText("Enviar mensaje");
  fireEvent.click(btn);
}

describe("SeccionChat", () => {
  it("muestra el empty state antes del primer mensaje", () => {
    render(<SeccionChat />);
    expect(
      screen.getByText(/Escríbele a Dona como lo harías por WhatsApp/i),
    ).toBeInTheDocument();
  });

  it("pinta el turno del usuario y la respuesta de Dona", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ respuesta: "Claro, con gusto." }),
    );
    render(<SeccionChat />);
    escribirYEnviar("hola dona");

    // El turno del usuario aparece de inmediato.
    expect(screen.getByText("hola dona")).toBeInTheDocument();
    // La respuesta de Dona aparece tras el fetch.
    await waitFor(() =>
      expect(screen.getByText("Claro, con gusto.")).toBeInTheDocument(),
    );

    // Se llamó a /api/chat con el mensaje.
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/chat");
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.mensaje).toBe("hola dona");
  });

  it("muestra 'escribiendo…' mientras espera", async () => {
    let resolver: (r: Response) => void = () => {};
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(
      () =>
        new Promise<Response>((res) => {
          resolver = res;
        }),
    );
    render(<SeccionChat />);
    escribirYEnviar("hola");

    // Aparece el indicador mientras el fetch está pendiente.
    await waitFor(() =>
      expect(screen.getByText(/Dona está escribiendo/i)).toBeInTheDocument(),
    );

    // Al resolver, desaparece y aparece la respuesta.
    resolver(jsonResponse({ respuesta: "Listo." }));
    await waitFor(() =>
      expect(screen.getByText("Listo.")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Dona está escribiendo/i)).not.toBeInTheDocument();
  });

  it("muestra burbuja de error ante 5xx sin perder el turno del usuario", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ error: "backend_unavailable" }, 502),
    );
    render(<SeccionChat />);
    escribirYEnviar("hola");

    expect(screen.getByText("hola")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText(/No pudimos procesar tu mensaje/i),
      ).toBeInTheDocument(),
    );
  });

  it("mapea 429 a un mensaje de 'vas muy rápido'", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ error: "rate_limit" }, 429),
    );
    render(<SeccionChat />);
    escribirYEnviar("spam");

    await waitFor(() =>
      expect(screen.getByText(/Vas muy rápido/i)).toBeInTheDocument(),
    );
  });

  it("muestra error de red cuando el fetch lanza", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("down"));
    render(<SeccionChat />);
    escribirYEnviar("hola");

    await waitFor(() =>
      expect(screen.getByText(/Sin conexión/i)).toBeInTheDocument(),
    );
  });
});

function adjuntarArchivo(container: HTMLElement, file: File) {
  const input = container.querySelector(
    'input[type="file"]',
  ) as HTMLInputElement;
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
}

describe("SeccionChat · media (Fase 3)", () => {
  it("muestra los controles de adjuntar y grabar", () => {
    render(<SeccionChat />);
    expect(screen.getByLabelText("Adjuntar imagen")).toBeInTheDocument();
    expect(screen.getByLabelText("Grabar nota de voz")).toBeInTheDocument();
  });

  it("adjunta una imagen y la envía en base64 (imagen_base64 + mime)", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ respuesta: "recibí tu imagen" }));
    const { container } = render(<SeccionChat />);
    // "hello" → base64 "aGVsbG8=" (jsdom no reduce en canvas: usa los bytes).
    adjuntarArchivo(
      container,
      new File(["hello"], "foto.png", { type: "image/png" }),
    );

    // Aparece el chip del adjunto con el nombre del archivo.
    await waitFor(() =>
      expect(screen.getByText("foto.png")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText("Enviar mensaje"));
    await waitFor(() =>
      expect(screen.getByText("recibí tu imagen")).toBeInTheDocument(),
    );

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/chat");
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.imagen_base64).toBe("aGVsbG8=");
    expect(body.imagen_mime).toBe("image/png");
  });

  it("permite quitar el adjunto antes de enviar", async () => {
    const { container } = render(<SeccionChat />);
    adjuntarArchivo(
      container,
      new File(["hello"], "foto.png", { type: "image/png" }),
    );
    await waitFor(() =>
      expect(screen.getByText("foto.png")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Quitar adjunto"));
    await waitFor(() =>
      expect(screen.queryByText("foto.png")).not.toBeInTheDocument(),
    );
  });

  it("rechaza un archivo que no es imagen con un aviso claro", async () => {
    const { container } = render(<SeccionChat />);
    adjuntarArchivo(
      container,
      new File(["%PDF"], "doc.pdf", { type: "application/pdf" }),
    );
    await waitFor(() =>
      expect(
        screen.getByText(/No pudimos leer el archivo/i),
      ).toBeInTheDocument(),
    );
  });

  it("avisa si el navegador no soporta grabar audio (jsdom sin MediaRecorder)", async () => {
    render(<SeccionChat />);
    fireEvent.click(screen.getByLabelText("Grabar nota de voz"));
    await waitFor(() =>
      expect(
        screen.getByText(/no permite grabar audio/i),
      ).toBeInTheDocument(),
    );
  });

  it("mapea 413 del backend a 'archivo muy grande'", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({ error: "adjunto_demasiado_grande" }, 413),
    );
    render(<SeccionChat />);
    escribirYEnviar("mira esta imagen");
    await waitFor(() =>
      expect(screen.getByText(/muy grande/i)).toBeInTheDocument(),
    );
  });

  it("doble click con getUserMedia en vuelo abre UN solo stream (anti-fuga de mic)", async () => {
    // MediaRecorder mínimo para jsdom.
    class FakeRec {
      state = "inactive";
      mimeType = "audio/webm";
      ondataavailable: ((e: unknown) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        this.onstop?.();
      }
      static isTypeSupported() {
        return true;
      }
    }
    const track = { stop: vi.fn() };
    const fakeStream = { getTracks: () => [track] } as unknown as MediaStream;
    // getUserMedia DIFERIDO: lo resolvemos a mano para simular la latencia del
    // prompt de permisos y disparar el segundo click en esa ventana.
    let resolverGUM: (s: MediaStream) => void = () => {};
    const getUserMedia = vi.fn(
      () => new Promise<MediaStream>((res) => (resolverGUM = res)),
    );

    const g = globalThis as unknown as { MediaRecorder?: unknown };
    const origMR = g.MediaRecorder;
    const origMD = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
    g.MediaRecorder = FakeRec;
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia },
      configurable: true,
    });
    try {
      render(<SeccionChat />);
      const mic = screen.getByLabelText("Grabar nota de voz");
      fireEvent.click(mic); // arranque #1 → getUserMedia queda pendiente
      fireEvent.click(mic); // #2 en la ventana → lo corta el guard síncrono
      // Pese a los dos clicks, sólo se pidió el micrófono UNA vez.
      expect(getUserMedia).toHaveBeenCalledTimes(1);
      resolverGUM(fakeStream);
      await waitFor(() =>
        expect(screen.getByLabelText("Detener grabación")).toBeInTheDocument(),
      );
    } finally {
      g.MediaRecorder = origMR;
      if (origMD) {
        Object.defineProperty(navigator, "mediaDevices", origMD);
      } else {
        Object.defineProperty(navigator, "mediaDevices", {
          value: undefined,
          configurable: true,
        });
      }
    }
  });
});
