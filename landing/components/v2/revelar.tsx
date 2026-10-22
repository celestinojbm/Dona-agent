"use client";

import { m, useReducedMotion } from "framer-motion";

const ENTRADA = [0.22, 1, 0.36, 1] as const;

// Si el usuario pide menos movimiento —o aún no lo sabemos (SSR)— el HTML
// queda en el estado final. La máscara y el stagger solo corren después.
export function Revelar({
  children,
  orden = 0,
  className,
}: {
  children: React.ReactNode;
  orden?: number;
  className?: string;
}) {
  const reducir = useReducedMotion();
  if (reducir !== false) {
    return <div className={className}>{children}</div>;
  }
  return (
    <m.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -8% 0px" }}
      transition={{ duration: 0.36, delay: orden * 0.05, ease: ENTRADA }}
    >
      {children}
    </m.div>
  );
}
