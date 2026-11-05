// Escala ▮▯▯▯ → ▮▮▮▮. Siempre junto a una etiqueta de texto: la forma no basta.

export function EscalaRiesgo({
  celdas,
  retardo = 0,
}: {
  celdas: number;
  /** Retraso base (ms) antes de llenar la primera celda. */
  retardo?: number;
}) {
  return (
    <span className="v2-escala" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className="v2-celda"
          data-on={i < celdas ? "true" : "false"}
          style={{ animationDelay: `${retardo + i * 80}ms` }}
        />
      ))}
    </span>
  );
}
