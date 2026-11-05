"use client";

import { LazyMotion, MotionConfig, domAnimation } from "framer-motion";

// domAnimation (sin layout/drag) mantiene el JS de movimiento por debajo
// del presupuesto. reducedMotion="user" apaga springs y whileInView.
export function ProveedorMovimiento({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domAnimation} strict>
        {children}
      </LazyMotion>
    </MotionConfig>
  );
}
