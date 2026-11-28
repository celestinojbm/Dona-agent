// landing/components/inicio-publico.tsx — Inicio público durante la pausa.
//
// Misma copia y mismos destinos que PaginaPausa. Solo cambia la presentación
// de `/`: ScrollReveal en el titular, SpotlightCard en la tarjeta, FadeContent
// en las secciones y StarBorder en los enlaces legales. El interruptor de
// pausa, el cobro y el acceso no se tocan. El texto sigue en el HTML.

import type { CSSProperties } from "react";
import FadeContent from "@/components/reactbits/FadeContent";
import ScrollReveal from "@/components/reactbits/ScrollReveal";
import SpotlightCard from "@/components/reactbits/SpotlightCard";
import StarBorder from "@/components/reactbits/StarBorder";
import { MENSAJE_PAUSA } from "@/lib/pausa";

const ENLACE =
  "cursor-pointer px-4 py-2 text-sm font-medium tracking-tight shadow-none";

export default function InicioPublico() {
  return (
    <main className="inicio-publico relative z-[2] flex min-h-screen items-center justify-center bg-[color:var(--bg)] px-6 py-16 text-[color:var(--ink)]">
      <SpotlightCard
        theme="light"
        spotlightColor="#111315"
        intensity={0.42}
        spotlightSize={220}
        softness={0.92}
        shape="circle"
        borderGlow={0.2}
        proximity={48}
        smoothing={0.45}
        ambient={false}
        flare={false}
        grain={0}
        className="w-full max-w-lg rounded-[1.25rem] p-10 sm:p-12"
        style={
          {
            "--spotlight-card-surface": "var(--surface)",
            "--spotlight-card-border": "var(--line)",
            "--spotlight-card-shadow":
              "0 1px 2px rgba(11, 11, 18, 0.03), 0 12px 32px -26px rgba(11, 11, 18, 0.16)",
          } as CSSProperties
        }
      >
        <FadeContent
          trigger="mount"
          effect="fade"
          blur={false}
          duration={0.4}
          initialOpacity={0.78}
        >
          <p className="text-2xl font-semibold tracking-tight">Dona</p>
          <p className="eyebrow mt-8">Servicio en pausa</p>
        </FadeContent>

        <ScrollReveal
          as="h1"
          enableBlur={false}
          baseRotation={0}
          baseOffset={0}
          baseOpacity={0.45}
          effect="fade"
          mode="enter"
          duration={0.55}
          stagger={0.04}
          containerClassName="mt-4 mb-0"
          textClassName="text-3xl font-medium leading-tight tracking-tight sm:text-4xl"
        >
          Dona está en pausa
        </ScrollReveal>

        <FadeContent
          trigger="mount"
          effect="fade"
          blur={false}
          duration={0.45}
          delay={0.05}
          initialOpacity={0.78}
        >
          <p className="mt-5 text-base leading-relaxed text-[color:var(--ink)]">{MENSAJE_PAUSA}</p>
        </FadeContent>

        <FadeContent
          trigger="mount"
          effect="fade"
          blur={false}
          duration={0.45}
          delay={0.08}
          initialOpacity={0.84}
        >
          <nav
            aria-label="Documentos legales"
            className="mt-10 flex flex-wrap gap-3 border-t border-[color:var(--line)] pt-6"
          >
            <StarBorder
              as="a"
              href="/terminos-y-condiciones"
              theme="light"
              color="#111315"
              trailColor="#3f3f4b"
              backgroundColor="var(--surface)"
              textColor="var(--muted)"
              borderColor="var(--line)"
              radius={999}
              thickness={1}
              duration={14}
              trailLength={0.18}
              stars={1}
              glow={0.16}
              sparkle={false}
              hover="none"
              clickPulse={false}
              className={ENLACE}
            >
              Términos y condiciones
            </StarBorder>
            <StarBorder
              as="a"
              href="/politica-de-privacidad"
              theme="light"
              color="#111315"
              trailColor="#3f3f4b"
              backgroundColor="var(--surface)"
              textColor="var(--muted)"
              borderColor="var(--line)"
              radius={999}
              thickness={1}
              duration={14}
              trailLength={0.18}
              stars={1}
              glow={0.16}
              sparkle={false}
              hover="none"
              clickPulse={false}
              className={ENLACE}
            >
              Política de privacidad
            </StarBorder>
          </nav>
        </FadeContent>

        <p className="mt-8 text-xs leading-relaxed text-[color:var(--muted)]">
          Animación con React Bits de David Haz, licencia MIT con Commons Clause.
        </p>
      </SpotlightCard>
    </main>
  );
}
