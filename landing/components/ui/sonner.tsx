"use client";

// Toaster (shadcn/ui · Sonner) re-vestido con el sistema v7 de Dona.
// Toast neutro y editorial: tarjeta blanca, borde y sombra del sistema,
// tipografía Plus Jakarta heredada. El error tiñe el texto con --dato-neg.
// Reemplaza los alert() nativos (feos y bloqueantes) por avisos no intrusivos.

import { Toaster as Sonner, type ToasterProps } from "sonner";
import { useTheme } from "next-themes";

const Toaster = (props: ToasterProps) => {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={resolvedTheme as ToasterProps["theme"]}
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "!rounded-2xl !border !border-[color:var(--line)] !bg-white !text-[color:var(--ink)] !shadow-[0_16px_40px_-18px_rgba(11,11,18,0.4)] !font-sans",
          title: "!text-[color:var(--ink)] !font-semibold",
          description: "!text-[color:var(--muted)]",
          error: "!text-[color:var(--dato-neg)]",
          actionButton: "!rounded-full !bg-[color:var(--ink)] !text-white",
          cancelButton: "!rounded-full !bg-[color:var(--fill)] !text-[color:var(--ink)]",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
