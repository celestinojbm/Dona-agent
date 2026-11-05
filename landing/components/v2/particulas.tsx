"use client";

import { useEffect, useRef } from "react";

// Puntos de tinta en el panel negro del hero. Sin Three.js.
// Solo en escritorio, con memoria holgada y sin reduced-motion.

const COLORES = ["#3F3F46", "#6B6B73"] as const;
const TOTAL = 48;

type Punto = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  color: string;
};

function puedeCorrer() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (window.innerWidth < 768) return false;
  const memoria = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  return typeof memoria === "number" && memoria >= 4;
}

export function Particulas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!puedeCorrer()) return;
    const canvas = ref.current;
    const panel = canvas?.parentElement;
    if (!canvas || !panel) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let frame = 0;
    let activo = false;
    let ancho = 0;
    let alto = 0;
    const mouse = { x: -999, y: -999, dentro: false };
    let puntos: Punto[] = [];

    const medir = () => {
      const rect = panel.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      ancho = rect.width;
      alto = rect.height;
      canvas.width = Math.max(1, Math.floor(ancho * dpr));
      canvas.height = Math.max(1, Math.floor(alto * dpr));
      canvas.style.width = `${ancho}px`;
      canvas.style.height = `${alto}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (puntos.length === 0) {
        puntos = Array.from({ length: TOTAL }, (_, i) => ({
          x: Math.random() * ancho,
          y: Math.random() * alto,
          vx: (Math.random() - 0.5) * 0.22,
          vy: (Math.random() - 0.5) * 0.22,
          r: i % 3 === 0 ? 1.6 : 1.1,
          color: COLORES[i % 2],
        }));
      }
    };

    const destino = (indice: number) => {
      const columna = indice % 4;
      const fila = Math.floor(indice / 4) % 6;
      const origenX = mouse.x + 18;
      const origenY = mouse.y - 28;
      const llena = columna < 2;
      return {
        x: origenX + columna * 10,
        y: origenY + fila * 4,
        visible: llena || fila === 0 || fila === 5,
      };
    };

    const dibujar = () => {
      if (!activo) return;
      ctx.clearRect(0, 0, ancho, alto);
      for (let i = 0; i < puntos.length; i += 1) {
        const punto = puntos[i];
        if (mouse.dentro && i < 24) {
          const meta = destino(i);
          if (meta.visible) {
            punto.x += (meta.x - punto.x) * 0.08;
            punto.y += (meta.y - punto.y) * 0.08;
          }
        } else {
          punto.x += punto.vx;
          punto.y += punto.vy;
          if (punto.x < 0 || punto.x > ancho) punto.vx *= -1;
          if (punto.y < 0 || punto.y > alto) punto.vy *= -1;
        }
        ctx.fillStyle = punto.color;
        ctx.beginPath();
        ctx.arc(punto.x, punto.y, punto.r, 0, Math.PI * 2);
        ctx.fill();
      }
      frame = window.requestAnimationFrame(dibujar);
    };

    const arrancar = () => {
      if (activo) return;
      activo = true;
      frame = window.requestAnimationFrame(dibujar);
    };
    const parar = () => {
      activo = false;
      window.cancelAnimationFrame(frame);
    };

    const onMove = (evento: PointerEvent) => {
      const rect = panel.getBoundingClientRect();
      mouse.x = evento.clientX - rect.left;
      mouse.y = evento.clientY - rect.top;
      mouse.dentro = true;
    };
    const onLeave = () => {
      mouse.dentro = false;
    };

    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((entrada) => entrada.isIntersecting)) arrancar();
        else parar();
      },
      { threshold: 0.15 },
    );

    medir();
    observador.observe(panel);
    panel.addEventListener("pointermove", onMove);
    panel.addEventListener("pointerleave", onLeave);
    window.addEventListener("resize", medir);

    return () => {
      parar();
      observador.disconnect();
      panel.removeEventListener("pointermove", onMove);
      panel.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("resize", medir);
    };
  }, []);

  return <canvas ref={ref} className="v2-particulas" aria-hidden="true" />;
}
