"use client";

// landing/app/engineering/panel-charts.tsx
// Primitivas de gráficos en SVG puro para el panel de ingeniería (sin libs:
// control total del look dark/editorial y cero peso extra en el bundle).
// Todas son presentacionales: reciben números ya calculados, no fetchean.

/** Paleta del panel: violeta Dona como acento + fríos para series. */
export const PALETA = [
  "#7C3AED", // violeta (acento Dona)
  "#2563EB", // azul eléctrico
  "#38bdf8", // celeste
  "#34d399", // esmeralda
  "#fbbf24", // ámbar
  "#64748b", // slate (Otros)
];

// ── Área con curva suave (Catmull-Rom → Bézier) ────────────────────────────

function pathSuave(pts: { x: number; y: number }[]): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

export function AreaChart({
  valores,
  etiquetas,
  alto = 170,
}: {
  valores: number[];
  /** Etiquetas alineadas con valores (para los <title> de hover). */
  etiquetas?: string[];
  alto?: number;
}) {
  const W = 600;
  const H = alto;
  const PAD = 8;
  if (valores.length === 0) return null;
  const max = Math.max(...valores, 1);
  const innerH = H - PAD * 2;
  const paso = valores.length > 1 ? (W - PAD * 2) / (valores.length - 1) : 0;
  const pts = valores.map((v, i) => ({
    x: PAD + i * paso,
    y: PAD + innerH - (v / max) * innerH,
  }));
  const linea = pathSuave(pts);
  const area = `${linea} L ${pts[pts.length - 1].x} ${H - PAD} L ${pts[0].x} ${H - PAD} Z`;
  const ultimo = pts[pts.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      style={{ height: alto }}
      preserveAspectRatio="none"
      role="img"
      aria-label="Commits por día"
    >
      <defs>
        <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7C3AED" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#7C3AED" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="areaLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#2563EB" />
          <stop offset="100%" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
      {/* líneas de referencia horizontales */}
      {[0.25, 0.5, 0.75].map((f) => (
        <line
          key={f}
          x1={PAD}
          x2={W - PAD}
          y1={PAD + innerH * f}
          y2={PAD + innerH * f}
          stroke="rgba(255,255,255,0.05)"
          strokeWidth="1"
        />
      ))}
      <path d={area} fill="url(#areaFill)" />
      <path
        d={linea}
        fill="none"
        stroke="url(#areaLine)"
        strokeWidth="2.5"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* puntos invisibles con tooltip nativo */}
      {pts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="7" fill="transparent">
          <title>{`${etiquetas?.[i] ?? i}: ${valores[i]} commits`}</title>
        </circle>
      ))}
      {/* Punto final como path de largo ~0 con cap redondo + stroke no
          escalable: con preserveAspectRatio="none" un <circle> se estira
          en elipse; el stroke con vectorEffect queda circular siempre. */}
      <path
        d={`M ${ultimo.x} ${ultimo.y} l 0.01 0`}
        stroke="#7C3AED"
        strokeWidth="16"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        fill="none"
        opacity="0.25"
      />
      <path
        d={`M ${ultimo.x} ${ultimo.y} l 0.01 0`}
        stroke="#7C3AED"
        strokeWidth="8"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        fill="none"
      />
    </svg>
  );
}

// ── Barras verticales (divs, alto proporcional) ────────────────────────────

export function BarrasV({
  valores,
  etiquetas,
  alto = 130,
  resaltarUltima = false,
}: {
  valores: number[];
  etiquetas?: string[];
  alto?: number;
  resaltarUltima?: boolean;
}) {
  const max = Math.max(...valores, 1);
  return (
    <div className="flex items-end gap-2" style={{ height: alto }}>
      {valores.map((v, i) => {
        const destacada = resaltarUltima && i === valores.length - 1;
        return (
          <div
            key={i}
            className="flex-1 flex flex-col items-center justify-end gap-1.5 h-full"
            title={`${etiquetas?.[i] ?? i}: ${v} commits`}
          >
            <span className="font-mono text-[10px] text-white/55 leading-none">
              {v}
            </span>
            <div
              className="w-full rounded-sm"
              style={{
                height: `${Math.max(3, (v / max) * 100)}%`,
                background: destacada
                  ? "linear-gradient(180deg, #7C3AED, #2563EB)"
                  : "rgba(255,255,255,0.14)",
              }}
            />
            {etiquetas && (
              <span className="font-mono text-[10px] text-white/50 leading-none">
                {etiquetas[i]}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Donut (lenguajes) ──────────────────────────────────────────────────────

export function Donut({
  partes,
  tamano = 150,
}: {
  partes: { nombre: string; valor: number }[];
  tamano?: number;
}) {
  const R = 42;
  const C = 2 * Math.PI * R;
  const total = partes.reduce((a, p) => a + p.valor, 0) || 1;
  // Offsets acumulados precalculados (inmutable: el compiler de React
  // prohíbe reasignar dentro del map del JSX). n ≤ 6, el O(n²) es gratis.
  const fracs = partes.map((p) => p.valor / total);
  const offsets = fracs.map((_, i) =>
    fracs.slice(0, i).reduce((a, b) => a + b, 0),
  );
  return (
    <svg
      viewBox="0 0 120 120"
      style={{ width: tamano, height: tamano }}
      role="img"
      aria-label="Distribución de lenguajes"
    >
      <circle
        cx="60"
        cy="60"
        r={R}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth="12"
      />
      {partes.map((p, i) => {
        const frac = fracs[i];
        const offset = offsets[i];
        return (
          <circle
            key={p.nombre}
            cx="60"
            cy="60"
            r={R}
            fill="none"
            stroke={PALETA[i % PALETA.length]}
            strokeWidth="12"
            strokeLinecap="butt"
            strokeDasharray={`${Math.max(0, frac * C - 1.5)} ${C}`}
            strokeDashoffset={-offset * C}
            transform="rotate(-90 60 60)"
          >
            <title>{`${p.nombre}: ${p.valor}%`}</title>
          </circle>
        );
      })}
      <text
        x="60"
        y="57"
        textAnchor="middle"
        fill="white"
        fontSize="16"
        fontWeight="300"
        fontFamily="var(--font-geist-mono), monospace"
      >
        {partes[0] ? `${Math.round(partes[0].valor)}%` : "—"}
      </text>
      <text
        x="60"
        y="72"
        textAnchor="middle"
        fill="rgba(255,255,255,0.4)"
        fontSize="8"
        fontFamily="var(--font-geist-mono), monospace"
      >
        {partes[0]?.nombre ?? ""}
      </text>
    </svg>
  );
}

// ── Sparkline (mini línea para KPIs) ───────────────────────────────────────

export function Sparkline({
  valores,
  color = "#7C3AED",
  ancho = 110,
  alto = 30,
}: {
  valores: number[];
  color?: string;
  ancho?: number;
  alto?: number;
}) {
  if (valores.length < 2) {
    return <div style={{ width: ancho, height: alto }} />;
  }
  const max = Math.max(...valores);
  const min = Math.min(...valores);
  const rango = max - min || 1;
  const paso = ancho / (valores.length - 1);
  const pts = valores.map((v, i) => ({
    x: i * paso,
    y: alto - 3 - ((v - min) / rango) * (alto - 6),
  }));
  const ultimo = pts[pts.length - 1];
  return (
    <svg
      viewBox={`0 0 ${ancho} ${alto}`}
      style={{ width: ancho, height: alto }}
      aria-hidden="true"
    >
      <path
        d={pathSuave(pts)}
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        opacity="0.9"
      />
      <circle cx={ultimo.x} cy={ultimo.y} r="2.4" fill={color} />
    </svg>
  );
}

// ── Anillo de porcentaje (success rate) ────────────────────────────────────

export function AnilloPct({
  pct,
  tamano = 64,
  color = "#34d399",
  etiqueta = "Porcentaje",
}: {
  /** 0–100, o null para estado desconocido. */
  pct: number | null;
  tamano?: number;
  color?: string;
  /** Nombre accesible de la métrica (coincide con el texto visible). */
  etiqueta?: string;
}) {
  const R = 26;
  const C = 2 * Math.PI * R;
  const frac = pct === null ? 0 : Math.max(0, Math.min(100, pct)) / 100;
  return (
    <svg
      viewBox="0 0 64 64"
      style={{ width: tamano, height: tamano }}
      role="img"
      aria-label={
        pct === null
          ? `${etiqueta}: sin datos`
          : `${etiqueta}: ${Math.round(pct)}%`
      }
    >
      <circle
        cx="32"
        cy="32"
        r={R}
        fill="none"
        stroke="rgba(255,255,255,0.08)"
        strokeWidth="5"
      />
      <circle
        cx="32"
        cy="32"
        r={R}
        fill="none"
        stroke={color}
        strokeWidth="5"
        strokeLinecap="round"
        strokeDasharray={`${frac * C} ${C}`}
        transform="rotate(-90 32 32)"
      />
      <text
        x="32"
        y="37"
        textAnchor="middle"
        fill="white"
        fontSize="14"
        fontWeight="300"
        fontFamily="var(--font-geist-mono), monospace"
      >
        {pct === null ? "—" : Math.round(pct)}
      </text>
    </svg>
  );
}

// ── Barra de progreso (roadmap estilo gantt) ───────────────────────────────

export function BarraProgreso({
  pct,
  color = "#7C3AED",
}: {
  pct: number;
  color?: string;
}) {
  return (
    <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
      <div
        className="h-full rounded-full"
        style={{
          width: `${Math.max(0, Math.min(100, pct))}%`,
          background: `linear-gradient(90deg, ${color}, #2563EB)`,
        }}
      />
    </div>
  );
}
