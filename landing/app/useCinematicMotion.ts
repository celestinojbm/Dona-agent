import { useEffect } from "react";

/**
 * useCinematicMotion — capa de movimiento GSAP de la landing (rediseño LTX).
 *
 * iter 1:
 *  - Parallax/zoom sutil del video de fondo a lo largo del hero.
 *  - Count-up REAL de las metricas (`[data-countup]`) al entrar en viewport.
 * iter 2:
 *  - Spotlight que sigue al mouse en las cards (`[data-spotlight]`), estilo
 *    Linear/LTX (un resplandor radial via las vars CSS --mx/--my).
 *
 * Progressive enhancement: respeta `prefers-reduced-motion` (no hace nada → los
 * numeros quedan en su valor real y las cards sin spotlight) y carga GSAP
 * dinamicamente (client-only) revirtiendo todo (tweens + listeners) al desmontar.
 */
export function useCinematicMotion() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let killed = false;
    let cleanup: (() => void) | undefined;

    (async () => {
      const gsapMod = await import("gsap");
      const stMod = await import("gsap/ScrollTrigger");
      if (killed) return;
      const gsap = gsapMod.gsap ?? gsapMod.default;
      const ScrollTrigger = stMod.ScrollTrigger ?? stMod.default;
      gsap.registerPlugin(ScrollTrigger);

      const removers: Array<() => void> = [];

      const ctx = gsap.context(() => {
        // 1. Zoom parallax del video de fondo durante el primer viewport de scroll.
        const video = document.querySelector("video");
        if (video) {
          gsap.fromTo(
            video,
            { scale: 1 },
            {
              scale: 1.15,
              ease: "none",
              scrollTrigger: {
                trigger: document.body,
                start: "top top",
                end: () => "+=" + window.innerHeight,
                scrub: 0.6,
              },
            }
          );
        }

        // 2. Count-up real de las metricas al entrar en vista.
        gsap.utils.toArray<HTMLElement>("[data-countup]").forEach((el) => {
          const target = parseFloat(el.dataset.countup || "0");
          if (!Number.isFinite(target)) return;
          const obj = { v: 0 };
          el.textContent = "0";
          ScrollTrigger.create({
            trigger: el,
            start: "top 88%",
            once: true,
            onEnter: () =>
              gsap.to(obj, {
                v: target,
                duration: 1.6,
                ease: "power2.out",
                onUpdate: () => {
                  el.textContent = String(Math.round(obj.v));
                },
                onComplete: () => {
                  el.textContent = String(target);
                },
              }),
          });
        });

        // 3. Spotlight que sigue al mouse en las cards (resplandor radial via
        //    --mx/--my; el gradiente vive en globals.css).
        gsap.utils.toArray<HTMLElement>("[data-spotlight]").forEach((card) => {
          const onMove = (e: MouseEvent) => {
            const r = card.getBoundingClientRect();
            card.style.setProperty("--mx", ((e.clientX - r.left) / r.width) * 100 + "%");
            card.style.setProperty("--my", ((e.clientY - r.top) / r.height) * 100 + "%");
          };
          card.addEventListener("mousemove", onMove);
          removers.push(() => card.removeEventListener("mousemove", onMove));
        });
      });

      cleanup = () => {
        removers.forEach((r) => r());
        ctx.revert();
      };
    })();

    return () => {
      killed = true;
      cleanup?.();
    };
  }, []);
}
