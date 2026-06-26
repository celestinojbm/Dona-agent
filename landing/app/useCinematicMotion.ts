import { useEffect, useLayoutEffect } from "react";

/**
 * useCinematicMotion — capa de movimiento GSAP de la landing (rediseño LTX).
 *
 * iter 1:
 *  - Parallax/zoom sutil del video de fondo a lo largo del hero.
 *  - Count-up REAL de las metricas (`[data-countup]`) al entrar en viewport.
 * iter 2:
 *  - Spotlight que sigue al mouse en las cards (`[data-spotlight]`), estilo
 *    Linear/LTX (un resplandor radial via las vars CSS --mx/--my).
 * iter 3:
 *  - Hover magnetico en los CTAs (`[data-magnetic]`): el boton se desplaza
 *    suavemente hacia el cursor y vuelve a su lugar al salir (estilo
 *    Linear/Higgsfield).
 * iter 4:
 *  - Titular kinetico (`[data-kinetic]` + `.kinetic-word`): reveal
 *    palabra-por-palabra del hero al cargar (rise + blur escalonado via
 *    transiciones CSS), firma visual tipo LTX/Higgsfield.
 * iter 6:
 *  - Barra de progreso de scroll (`.scroll-beam`): un haz fino con el degradado
 *    de marca (azul→naranja) fijado arriba que se llena de izquierda a derecha
 *    segun el avance del scroll (scrubbed), firma tipo Linear/Vercel/LTX.
 * iter 11:
 *  - Campo de luz ambiental (`.ambient-blob`): los pozos de luz de color del
 *    fondo derivan a distinta profundidad a lo largo del scroll de toda la
 *    pagina (parallax via transform GPU, scrub), dando una atmosfera
 *    cinematografica viva tipo LTX/Higgsfield.
 *
 * Progressive enhancement: respeta `prefers-reduced-motion` (no hace nada → los
 * numeros quedan en su valor real, las cards sin spotlight y el titular visible)
 * y carga GSAP dinamicamente (client-only) revirtiendo todo (tweens + listeners)
 * al desmontar.
 */
export function useCinematicMotion() {
  // Titular kinetico (iter 4): reveal palabra-por-palabra del hero. Lo hacemos
  // con transiciones CSS (mismo patron probado que FadeIn) en vez de un tween
  // GSAP, para no chocar con el doble-montaje de React Strict Mode ni con la
  // carga asincrona de GSAP. Pre-paint marcamos el titular como "pending" (las
  // palabras arrancan ocultas via CSS) solo con JS y sin reduced-motion — asi no
  // hay flash. En el siguiente frame pasamos a "visible" y cada palabra entra con
  // su propio delay (--ki). Sin JS o con reduced-motion el atributo queda en su
  // valor inicial y las palabras se ven completas (nunca dejamos el titular
  // invisible).
  useLayoutEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const headline = document.querySelector<HTMLElement>("[data-kinetic]");
    if (!headline) return;
    headline.setAttribute("data-kinetic", "pending");
    const raf1 = requestAnimationFrame(() =>
      requestAnimationFrame(() => headline.setAttribute("data-kinetic", "visible"))
    );
    return () => cancelAnimationFrame(raf1);
  }, []);

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

        // 4. Hover magnetico en los CTAs: el boton sigue suavemente al cursor
        //    (gsap.quickTo da el spring-back) y vuelve a 0,0 al salir.
        gsap.utils.toArray<HTMLElement>("[data-magnetic]").forEach((btn) => {
          const xTo = gsap.quickTo(btn, "x", { duration: 0.5, ease: "power3.out" });
          const yTo = gsap.quickTo(btn, "y", { duration: 0.5, ease: "power3.out" });
          const strength = 0.4; // fraccion del desplazamiento cursor→centro
          const onMove = (e: MouseEvent) => {
            const r = btn.getBoundingClientRect();
            xTo((e.clientX - (r.left + r.width / 2)) * strength);
            yTo((e.clientY - (r.top + r.height / 2)) * strength);
          };
          const onLeave = () => {
            xTo(0);
            yTo(0);
          };
          btn.addEventListener("mousemove", onMove);
          btn.addEventListener("mouseleave", onLeave);
          removers.push(() => {
            btn.removeEventListener("mousemove", onMove);
            btn.removeEventListener("mouseleave", onLeave);
          });
        });

        // 5. Barra de progreso de scroll: el haz superior se escala en X de 0→1
        //    a lo largo de todo el documento (scrub). Sin reduced-motion (todo
        //    este efecto se salta) la barra queda en scaleX(0) → invisible.
        const beam = document.querySelector<HTMLElement>(".scroll-beam");
        if (beam) {
          gsap.fromTo(
            beam,
            { scaleX: 0 },
            {
              scaleX: 1,
              ease: "none",
              scrollTrigger: {
                trigger: document.body,
                start: "top top",
                end: "bottom bottom",
                scrub: 0.3,
              },
            }
          );
        }

        // 6. Campo de luz ambiental: los blobs del fondo derivan a distinta
        //    profundidad a lo largo del scroll de toda la pagina (parallax via
        //    transform GPU + scrub). Distintos yPercent/xPercent dan la
        //    sensacion de capas. ctx.revert() limpia tweens y ScrollTriggers.
        const ambientDrift: Array<[string, number, number]> = [
          [".ambient-blob--violet", 38, 8],
          [".ambient-blob--blue", -30, -10],
          [".ambient-blob--amber", 24, 12],
        ];
        ambientDrift.forEach(([selector, yPercent, xPercent]) => {
          if (!document.querySelector(selector)) return;
          gsap.to(selector, {
            yPercent,
            xPercent,
            ease: "none",
            scrollTrigger: {
              trigger: document.body,
              start: "top top",
              end: "bottom bottom",
              scrub: 0.8,
            },
          });
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
