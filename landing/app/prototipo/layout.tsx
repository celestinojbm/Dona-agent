import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./hero.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-hero-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-hero-mono",
  display: "swap",
});

// Pausa: la página responde 404 (ver page.tsx). Sin título de prototipo y
// fuera de los buscadores.
export const metadata: Metadata = {
  title: "Dona",
  robots: { index: false, follow: false },
};

export default function PrototipoLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <div className={`${sans.variable} ${mono.variable}`}>{children}</div>;
}
