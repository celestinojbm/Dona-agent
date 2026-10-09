// landing/lib/backend-url.ts — BACKEND_URL validado (J4).
//
// Único punto que lee BACKEND_URL para los bridges server-side. Antes cada
// bridge hacía `process.env.BACKEND_URL?.trim()` y aceptaba cualquier
// cadena; con el backend moviéndose de Render a la MSI (túnel), una URL mal
// escrita no debe convertirse en peticiones a un host arbitrario.
//
// Reglas:
//   - URL absoluta parseable, sin usuario/contraseña, sin query ni fragmento.
//   - En producción (NODE_ENV=production): solo https, salvo http a loopback
//     (localhost, 127.0.0.1, [::1]) para pruebas locales del build.
//   - Se devuelve normalizada, sin "/" final (los bridges concatenan
//     `${url}/internal/...`).
//   - Inválida → null, igual que ausente: el bridge responde
//     backend_url_missing. El valor nunca se escribe en el log.

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function resolverBackendUrl(
  valor: string | undefined = process.env.BACKEND_URL,
): string | null {
  const crudo = valor?.trim();
  if (!crudo) return null;

  let url: URL;
  try {
    url = new URL(crudo);
  } catch {
    console.error("[BACKEND-URL] BACKEND_URL no es una URL válida");
    return null;
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    console.error("[BACKEND-URL] BACKEND_URL debe ser http(s)");
    return null;
  }
  if (url.username || url.password || url.search || url.hash) {
    console.error("[BACKEND-URL] BACKEND_URL no admite credenciales, query ni fragmento");
    return null;
  }
  if (
    process.env.NODE_ENV === "production" &&
    url.protocol === "http:" &&
    !LOOPBACK.has(url.hostname)
  ) {
    console.error("[BACKEND-URL] BACKEND_URL debe ser https en producción");
    return null;
  }

  return `${url.origin}${url.pathname}`.replace(/\/+$/, "");
}
