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
