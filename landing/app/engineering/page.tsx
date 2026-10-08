// landing/app/engineering/page.tsx
// Panel de ingeniería personal del dueño (GitHub + Actions + Render).
//
// Durante la pausa la ruta no existe para nadie (404): era una superficie
// pública con login propio y credenciales de cuenta (GitHub/Render) en el
// servidor. El panel (panel-client, login-form) queda en el repo sin ruta
// que lo monte; sus APIs (/api/engineering/*) también responden 404.

import type { Metadata } from "next";
import { notFound } from "next/navigation";

export const metadata: Metadata = {
  title: "Dona",
  robots: { index: false, follow: false },
};

export default function EngineeringPage() {
  notFound();
}
