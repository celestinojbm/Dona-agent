// landing/app/interno/control-room/page.tsx — Control Room interno.
//
// Fuera de la app del cliente: ya no es una sección del dashboard ni aparece
// en su navegación. El gate corre en el servidor en cada petición:
//
//   - Durante la pausa responde 404 para todos.
//   - Sin sesión, con un correo fuera de la allowlist o sin la cookie del
//     token del dueño (lib/control-room, solo servidor) responde 404, igual
//     que una ruta inexistente: no revela que hay un panel detrás. El correo
//     de la sesión sale de Stripe y no está verificado; el token sí prueba
//     que es el dueño.
//
// El panel es un componente de servidor: el índice de agent-runs y los
// textos internos se renderizan aquí y nunca entran en el bundle cliente.

import type { Metadata } from "next";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { DONA_EN_PAUSA } from "@/lib/pausa";
import { puedeVerControlRoomInterno } from "@/lib/control-room";
import { PANEL_COOKIE } from "@/lib/panel-auth";
import PanelControlRoom from "./panel-control-room";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Dona",
  robots: { index: false, follow: false },
};

export default async function ControlRoomPage() {
  if (DONA_EN_PAUSA) notFound();

  const session = await auth();
  const tokenPanel = (await cookies()).get(PANEL_COOKIE)?.value;
  if (!puedeVerControlRoomInterno(session?.user?.email, tokenPanel)) notFound();

  return (
    <main className="relative z-[2] min-h-screen bg-[color:var(--bg)] px-5 py-8 text-[color:var(--ink)] md:px-10 md:py-10">
      <div className="mx-auto max-w-5xl">
        <PanelControlRoom />
      </div>
    </main>
  );
}
