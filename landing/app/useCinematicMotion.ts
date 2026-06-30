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
 * iter 5:
 *  - Parallax de profundidad (`[data-parallax]`): los numerales gigantes
 *    (bloque de dolor y pasos de "Como funciona") hacen drift en scroll a
 *    distinta velocidad que su texto, dando capas de profundidad cinematografica.
 * iter 6:
 *  - Barra de progreso de scroll (`.scroll-beam`): un haz fino con el degradado
 *    de marca (azul→naranja) fijado arriba que se llena de izquierda a derecha
 *    segun el avance del scroll (scrubbed), firma tipo Linear/Vercel/LTX.
 * iter 9:
 *  - Reveal escalonado de las cards (`[data-reveal-group]` + `[data-reveal]`):
 *    al entrar en vista, las cards de cada grid entran en cascada (translate +
 *    scale + blur con stagger) via `ScrollTrigger.batch`, estilo LTX.
 * iter 11:
 *  - Campo de luz ambiental (`.ambient-blob`): los pozos de luz de color del
 *    fondo derivan a distinta profundidad a lo largo del scroll de toda la
 *    pagina (parallax via transform GPU, scrub), dando una atmosfera
 *    cinematografica viva tipo LTX/Higgsfield.
 * iter 13:
 *  - Scroll-away del hero (`[data-hero-scroll]`): el bloque del hero deriva
 *    hacia arriba y se desvanece a medida que sales del primer viewport, como si
 *    el heroe retrocediera en profundidad (firma cinematografica tipo LTX).
 *    Scrubbeado al scroll sobre el alto del hero.
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

    // Reveal escalonado (iter 9): marcamos cada grid como "ready" pre-paint para
    // que CSS oculte sus cards [data-reveal] antes del primer frame (sin flash).
    // GSAP las revela luego al entrar en vista; al desmontar volvemos a "idle"
    // para que las cards queden visibles si GSAP no llega a correr.
    const groups = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal-group]"));
    groups.forEach((g) => g.setAttribute("data-reveal-group", "ready"));

    const headline = document.querySelector<HTMLElement>("[data-kinetic]");
    if (headline) headline.setAttribute("data-kinetic", "pending");
    const raf1 = requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        if (headline) headline.setAttribute("data-kinetic", "visible");
      })
    );
    return () => {
      cancelAnimationFrame(raf1);
      groups.forEach((g) => g.setAttribute("data-reveal-group", "idle"));
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let killed = false;
    let cleanup: (() => void) | undefined;

    // Si GSAP no llega a cargar (red, bloqueo), revelamos las cards que ocultamos
    // pre-paint para no dejarlas invisibles: el reveal es enhancement, no requisito.
    const revelarFallback = () =>
      document
        .querySelectorAll<HTMLElement>('[data-reveal-group="ready"]')
        .forEach((g) => g.setAttribute("data-reveal-group", "shown"));

    (async () => {
      let gsapMod: typeof import("gsap");
      let stMod: typeof import("gsap/ScrollTrigger");
      try {
        gsapMod = await import("gsap");
        stMod = await import("gsap/ScrollTrigger");
      } catch {
        revelarFallback();
        return;
      }
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
                scrub: true,
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

        // 7. Parallax de profundidad en los numerales gigantes: cada elemento
        //    [data-parallax] hace drift vertical mientras cruza el viewport
        //    (scrub al scroll), a una velocidad propia (atributo = fraccion).
        //    Como solo translada (transform), no altera el layout ni provoca
        //    scroll horizontal; el texto que lo acompaña queda fijo → capas.
        gsap.utils.toArray<HTMLElement>("[data-parallax]").forEach((el) => {
          const speed = parseFloat(el.dataset.parallax || "0.2");
          if (!Number.isFinite(speed)) return;
          gsap.fromTo(
            el,
            { yPercent: speed * 40 },
            {
              yPercent: -speed * 40,
              ease: "none",
              scrollTrigger: {
                trigger: el,
                start: "top bottom",
                end: "bottom top",
                scrub: 0.6,
              },
            }
          );
        });

        // 8. Scroll-away del hero (iter 13): el bloque del hero [data-hero-scroll]
        //    deriva hacia arriba y se desvanece mientras sales del primer viewport,
        //    como si retrocediera en profundidad. Trigger sobre la propia seccion
        //    del hero (start cuando su top toca el top del viewport, end cuando su
        //    bottom toca el top), scrubbeado para que sea continuo. Solo transform
        //    + opacity, sin reflow. Sin JS / reduced-motion el bloque queda intacto.
        const heroBlock = document.querySelector<HTMLElement>("[data-hero-scroll]");
        if (heroBlock) {
          gsap.fromTo(
            heroBlock,
            { y: 0, opacity: 1 },
            {
              y: -120,
              opacity: 0,
              ease: "none",
              scrollTrigger: {
                trigger: heroBlock.closest("section") ?? heroBlock,
                start: "top top",
                end: "bottom top",
                scrub: 0.5,
              },
            }
          );
        }

        // 9. Reveal escalonado de las cards: cada grid [data-reveal-group] revela
        //    sus hijos [data-reveal] en cascada al entrar en vista (translate +
        //    scale + blur con stagger). El estado oculto inicial lo pone CSS via el
        //    atributo "ready" seteado pre-paint (sin flash); aqui los traemos a su
        //    estado natural. Disparamos con IntersectionObserver nativo (fiable,
        //    mismo mecanismo que FadeIn) y usamos GSAP solo para el tween escalonado
        //    — asi el reveal no depende del scroll-detection de ScrollTrigger.
        //    En cuanto el grid entra en vista pasamos el atributo a "shown" para que
        //    CSS mantenga las cards visibles aunque un ctx.revert() de otra capa
        //    borre los inline-styles del tween (el reveal no debe poder revertirse a
        //    oculto). El onComplete vuelve a fijarlo por si el tween corre primero.
        gsap.utils.toArray<HTMLElement>("[data-reveal-group]").forEach((group) => {
          const items = gsap.utils.toArray<HTMLElement>("[data-reveal]", group);
          if (!items.length) return;
          const io = new IntersectionObserver(
            (entries, obs) => {
              if (!entries.some((e) => e.isIntersecting)) return;
              obs.disconnect();
              group.setAttribute("data-reveal-group", "shown");
              // fromTo con immediateRender: GSAP fija el estado oculto inicial
              // (los mismos valores que la regla CSS [data-reveal-group="ready"])
              // y anima hasta visible. Asi la cascada no depende de que el atributo
              // siga en "ready" — ya lo pasamos a "shown" arriba para sobrevivir a
              // un ctx.revert() de otra capa sin volver a ocultar las cards. Si
              // animaramos con gsap.to() la animacion se perderia: leeria el estado
              // de inicio cuando el atributo ya es "shown" (visible) → sin cascada.
              gsap.fromTo(
                items,
                { opacity: 0, y: 40, scale: 0.96, filter: "blur(6px)" },
                {
                  opacity: 1,
                  y: 0,
                  scale: 1,
                  filter: "blur(0px)",
                  duration: 0.9,
                  ease: "power3.out",
                  stagger: 0.1,
                  overwrite: true,
                  onComplete: () => {
                    group.setAttribute("data-reveal-group", "shown");
                    items.forEach((el) => {
                      el.style.willChange = "auto";
                    });
                  },
                }
              );
            },
            { rootMargin: "-80px" }
          );
          io.observe(group);
          removers.push(() => io.disconnect());
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
