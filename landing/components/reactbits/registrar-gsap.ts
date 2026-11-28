// landing/components/reactbits/registrar-gsap.ts
// ScrollTrigger toca matchMedia al registrarse. En el navegador ya existe;
// en jsdom (vitest) no, y el import no debe tirar la página ni los tests.

import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

let registrado = false;

export function registrarScrollTrigger() {
  if (typeof window === "undefined" || registrado) return;
  if (typeof window.matchMedia !== "function") {
    window.matchMedia = (query: string): MediaQueryList =>
      ({
        matches: false,
        media: query,
        onchange: null,
        addListener() {},
        removeListener() {},
        addEventListener() {},
        removeEventListener() {},
        dispatchEvent() {
          return false;
        },
      }) as MediaQueryList;
  }
  gsap.registerPlugin(ScrollTrigger);
  registrado = true;
}
