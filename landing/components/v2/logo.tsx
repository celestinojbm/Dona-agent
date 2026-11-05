// Marca de Dona. El fucsia #E64263 vive SOLO en el punto de la «d».

type Tono = "tinta" | "blanco";

export function Logo({ tono = "tinta" }: { tono?: Tono }) {
  const tinta = tono === "blanco" ? "#FFFFFF" : "#0B0B12";
  return (
    <span className={`v2-logo v2-logo-${tono}`}>
      <svg viewBox="10 6 80 98" className="v2-logo-marca" aria-hidden="true">
        <circle cx="50" cy="56" r="30" fill="none" stroke={tinta} strokeWidth="14" />
        <rect x="73" y="8" width="14" height="78" rx="7" fill={tinta} />
        <circle cx="80" cy="92" r="7" fill="#E64263" />
      </svg>
      <span className="v2-logo-nombre">dona</span>
    </span>
  );
}
