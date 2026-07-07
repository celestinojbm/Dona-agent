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

export const metadata: Metadata = {
  title: "Dona — prototipo hero v2",
  description: "Prototipo de dirección visual: base clara premium + vitalidad de gradiente.",
};

export default function PrototipoLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <div className={`${sans.variable} ${mono.variable}`}>{children}</div>;
}
