import type { Metadata } from "next";
import { Outfit, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const mono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Dona — Plataforma-agente de negocio y ejecucion",
  description:
    "Dona convierte tu intencion en activos, workflows, documentos, campañas y acciones reales — con creditos, permisos, trazabilidad y medicion. Plataforma-agente de negocio para emprendedores hispanos.",
  metadataBase: new URL("https://usadona.com"),
  openGraph: {
    title: "Dona — Plataforma-agente de negocio y ejecucion",
    description:
      "Convierte intencion en ejecucion controlada: activos, workflows, campañas y acciones reales, con permiso y medicion.",
    url: "https://usadona.com",
    siteName: "Dona",
    locale: "es_MX",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Dona — Plataforma-agente de negocio y ejecucion",
    description:
      "Convierte intencion en ejecucion controlada: activos, workflows, campañas y acciones reales, con permiso y medicion.",
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
      className={`${outfit.variable} ${mono.variable} h-full antialiased`}
    >
      <head>
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
          />
        </noscript>
      </head>
      <body className="noise-overlay min-h-full flex flex-col relative bg-black">
        {/* Global video background */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="fixed inset-0 w-full h-full object-cover z-0"
          aria-hidden="true"
        >
          <source src="/hero.mp4" type="video/mp4" />
        </video>
        <div
          className="fixed inset-0 bg-black/[0.72] z-[1] pointer-events-none"
          aria-hidden="true"
        />
        <div className="relative z-10 flex flex-col min-h-full">
          {children}
        </div>
      </body>
    </html>
  );
}
