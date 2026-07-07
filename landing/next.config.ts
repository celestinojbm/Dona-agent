import type { NextConfig } from "next";

// Content-Security-Policy de la landing.
//
// Orígenes permitidos y por qué:
// - 'self' como default-src: todo lo demás debe listarse explícitamente.
// - connect.facebook.net en script-src: carga fbevents.js (Facebook Pixel,
//   ver app/layout.tsx). Es el único script de terceros en toda la landing
//   (confirmado por grep: no hay GTM, gtag, chat widgets ni otros SDKs
//   client-side).
// - www.facebook.com en img-src/connect-src: el pixel hace beacon de
//   tracking (fbq('track', ...)) hacia www.facebook.com/tr, tanto vía
//   imagen <noscript> como vía fetch/XHR del propio fbevents.js.
// - 'unsafe-inline' en script-src: el snippet del pixel es un <script>
//   inline con dangerouslySetInnerHTML (no hay middleware.ts en este
//   proyecto para cablear nonces por request). Deuda técnica: migrar a
//   nonce vía middleware si en el futuro se agregan más scripts inline.
// - 'unsafe-inline' en style-src: Next.js/styled-jsx inyectan estilos
//   inline en runtime; sin esto se rompen los estilos base de Next.
// - No se permiten fonts.googleapis.com/fonts.gstatic.com: las fuentes
//   (Outfit, JetBrains Mono) se autoalojan vía next/font/google, que las
//   sirve desde 'self' en build time — no hay fetch remoto a Google Fonts.
// - No se permiten dominios de Stripe: el checkout (app/api/checkout)
//   corre 100% server-side vía Stripe SDK y redirige a una URL de Stripe
//   Checkout hospedada (session.url) — no hay Stripe.js ni Stripe Elements
//   en el cliente, así que no hace falta abrir script-src/connect-src/
//   frame-src para js.stripe.com/api.stripe.com.
// - frame-ancestors 'none': refuerza X-Frame-Options: DENY (ningún
//   auto-embedding encontrado en la app).
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://connect.facebook.net",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https://www.facebook.com",
  "connect-src 'self' https://www.facebook.com",
  "font-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  // Sin auto-embedding encontrado en la app: bloquea framing por completo.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Cámara, micrófono y geolocalización no se usan en ningún punto de la
  // landing (confirmado por grep de mediaDevices/getUserMedia/geolocation).
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/hero.mp4",
        headers: [
          { key: "Accept-Ranges", value: "bytes" },
          { key: "Content-Type", value: "video/mp4" },
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
