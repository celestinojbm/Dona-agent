// landing/lib/planes.ts — Catálogo de DISPLAY de los planes de suscripción.
//
// Única fuente de verdad para lo que se MUESTRA de cada plan (nombre, precio,
// features) — la usan la sección de pricing de la landing (app/page.tsx) y la
// página de checkout (app/checkout). Los price IDs y montos que Stripe cobra
// viven aparte en lib/stripe.ts (server-side): este módulo es seguro de
// importar desde el cliente.
//
// Las claves de `plan` son las que espera el backend/checkout: "premium"|"pro".

export interface PlanDisplay {
  plan: "premium" | "pro";
  nombre: string;
  precio: string;
  periodo: string;
  features: string[];
  destacado: boolean;
}

export const PLANES_DISPLAY: PlanDisplay[] = [
  {
    plan: "premium",
    nombre: "Premium",
    precio: "$20",
    periodo: "/mes",
    features: [
      "Studio, Flow y Memory",
      "Acciones con preview y aprobación",
      "Créditos incluidos cada mes",
      "Entrada por WhatsApp, web, app y voz",
      "Audit trail y límites de gasto",
      "Soporte prioritario",
    ],
    destacado: false,
  },
  {
    plan: "pro",
    nombre: "Pro",
    precio: "$40",
    periodo: "/mes",
    features: [
      "Todo lo de Premium",
      "Agents con límites por herramienta",
      "Control Room y medición avanzada",
      "Integraciones y automatizaciones",
      "Multi-negocio",
      "Más créditos incluidos",
    ],
    destacado: true,
  },
];

export type PlanCheckout = PlanDisplay["plan"];

export function esPlanValido(valor: string | null): valor is PlanCheckout {
  return valor === "premium" || valor === "pro";
}
