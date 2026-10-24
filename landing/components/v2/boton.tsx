import Link from "next/link";
import { ArrowRight } from "lucide-react";

type Variante = "primario" | "secundario" | "texto" | "sobre-negro";

export function Boton({
  href,
  variante = "primario",
  children,
  flecha = false,
  className = "",
}: {
  href: string;
  variante?: Variante;
  children: React.ReactNode;
  flecha?: boolean;
  className?: string;
}) {
  return (
    <Link href={href} className={`v2-btn v2-btn-${variante} ${className}`.trim()}>
      {children}
      {flecha ? <ArrowRight size={16} strokeWidth={1.5} aria-hidden="true" /> : null}
    </Link>
  );
}
