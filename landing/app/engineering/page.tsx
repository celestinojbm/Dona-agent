// landing/app/engineering/page.tsx
// Panel de ingeniería personal del dueño — progreso real del proyecto Dona
// conectado al repo (GitHub + Actions + Render). NO es el dashboard de
// producto del usuario final.
//
// Gate de acceso: cookie httpOnly con el token del dueño (PANEL_INGENIERIA_
// TOKEN), validada server-side en cada render y en cada poll de datos.

import type { Metadata } from "next";
import { cookies } from "next/headers";
import { esTokenPanelValido, PANEL_COOKIE } from "@/lib/panel-auth";
import type { Roadmap } from "@/lib/panel-types";
import roadmapJson from "@/data/panel-roadmap.json";
import PanelClient from "./panel-client";
import LoginForm from "./login-form";

export const metadata: Metadata = {
  title: "Engineering — Dona",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default async function EngineeringPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get(PANEL_COOKIE)?.value;

  if (!esTokenPanelValido(token)) {
    return <LoginForm />;
  }

  return <PanelClient roadmap={roadmapJson as Roadmap} />;
}
