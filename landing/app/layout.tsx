import type { Metadata } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Base clara editorial: Plus Jakarta Sans (grotesca suave, la misma de la
// referencia Merxo) para titulares y lectura; JetBrains Mono para labels
// técnicos (métricas, estados de agentes, créditos). Ambas autoalojadas vía
// next/font (se sirven desde 'self', sin fetch a Google Fonts — la CSP no
// abre fonts.gstatic.com).
const sans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-hero-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-hero-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Dona — Plataforma-agente de negocio y ejecución",
  description:
    "Dona convierte intención en ejecución real: activos, workflows, documentos, campañas y acciones reales — con permisos, créditos, trazabilidad y medición. Empieza desde WhatsApp, web o voz.",
  metadataBase: new URL("https://usadona.com"),
  openGraph: {
    title: "Dona — Plataforma-agente de negocio y ejecución",
    description:
      "Convierte intención en ejecución controlada: activos, workflows, campañas y acciones reales, con permiso y medición.",
    url: "https://usadona.com",
    siteName: "Dona",
    locale: "es_MX",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Dona — Plataforma-agente de negocio y ejecución",
    description:
      "Convierte intención en ejecución controlada: activos, workflows, campañas y acciones reales, con permiso y medición.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <head>
        {/* Facebook Pixel — único script de terceros. El snippet inline se
            permite por 'unsafe-inline' en script-src (ver next.config.ts).
            NO tocar la CSP: el pixel sigue funcionando tal cual. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '26253527804332195');
fbq('track', 'PageView');`,
          }}
        />
        <noscript>
          <img
            height="1"
            width="1"
            style={{ display: "none" }}
            src="https://www.facebook.com/tr?id=26253527804332195&ev=PageView&noscript=1"
            alt=""
          />
        </noscript>
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
