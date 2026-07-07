"use client";

// landing/app/dashboard/seccion-galeria.tsx
// Galería de Activos · lo que Dona ya generó para el usuario, visible en web.
//
// Fase 1 (plataforma web): el usuario ve en el dashboard los activos que
// antes sólo recibía por WhatsApp (imágenes, videos, docs, audios, webs).
// Los datos vienen de /api/assets → /internal/assets (backend), que resuelve
// telefono desde la sesión y sólo devuelve los activos de ese usuario.
//
// Decisiones de UX:
//   - Solo lectura: ver y descargar. Generar activos sigue viviendo en el
//     chat (WhatsApp) / flujos creativos; esta superficie no cobra ni crea.
//   - Imágenes muestran preview real (<img src=url_publica>); el resto un
//     ícono por tipo. Un fallback cubre imágenes cuya URL ya no cargue.
//   - Empty state con gracia: "Aún no has generado activos".
//   - Orden del backend (más reciente primero) · no reordenamos.

import { useCallback, useEffect, useState } from "react";
import {
  Image as ImageIcon,
  Play,
  Mic,
  Globe,
  FileText,
  Loader2,
  RefreshCw,
  Download,
} from "lucide-react";
import type {
  AssetGaleria,
  AssetsResponse,
  TipoAsset,
} from "@/lib/assets-types";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: AssetsResponse }
  | { status: "error"; code: string };

const TIPO_ICONO: Record<TipoAsset, typeof ImageIcon> = {
  image: ImageIcon,
  video: Play,
  audio: Mic,
  web: Globe,
  doc: FileText,
};

const TIPO_LABEL: Record<TipoAsset, string> = {
  image: "Imagen",
  video: "Video",
  audio: "Audio",
  web: "Web",
  doc: "Documento",
};

function formatFechaIso(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("es-MX", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function SeccionGaleria() {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });

  const fetchAssets = useCallback(async () => {
    try {
      const res = await fetch("/api/assets", { cache: "no-store" });
      if (!res.ok) {
        setLoad({ status: "error", code: `error_${res.status}` });
        return;
      }
      const data = (await res.json()) as AssetsResponse;
      setLoad({ status: "ready", data });
    } catch {
      setLoad({ status: "error", code: "network_error" });
    }
  }, []);

  useEffect(() => {
    setLoad({ status: "loading" });
    void fetchAssets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const data = load.status === "ready" ? load.data : null;
  const assets = data?.assets ?? [];

  return (
    <section>
      <h2 className="text-sm uppercase tracking-[0.2em] text-white/25 font-light mb-6 flex items-center gap-2">
        <ImageIcon className="w-4 h-4" />
        Galería
      </h2>

      {/* Aviso UX general */}
      <div className="glass-card rounded-2xl px-6 py-5 mb-4 border-white/[0.06]">
        <p className="text-sm text-white/55 font-light leading-relaxed">
          Todo lo que Dona ha generado para ti — imágenes, videos, documentos
          y más — reunido aquí para verlo y descargarlo cuando quieras.
        </p>
      </div>

      {/* Contador + refrescar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-xs text-white/35 font-light">
          {load.status === "ready"
            ? `${assets.length} ${assets.length === 1 ? "activo" : "activos"}`
            : "Cargando activos…"}
        </p>
        <button
          onClick={fetchAssets}
          disabled={load.status === "loading"}
          className="btn-secondary px-5 py-2.5 rounded-full text-sm flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {load.status === "loading" ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Actualizar
        </button>
      </div>

      {/* Loading */}
      {load.status === "loading" && (
        <div className="glass-card rounded-2xl p-8 text-center">
          <p className="text-white/35 font-light">Cargando…</p>
        </div>
      )}

      {/* Error real */}
      {load.status === "error" && (
        <div className="glass-card rounded-2xl p-8 border-rose-500/15">
          <p className="text-white/70 font-light">
            No pudimos cargar tu galería.
          </p>
          <p className="text-xs text-white/35 font-light mt-1 font-mono">
            {load.code}
          </p>
          <button
            onClick={fetchAssets}
            className="btn-secondary px-5 py-2 rounded-full text-sm mt-3"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Empty state */}
      {load.status === "ready" && assets.length === 0 && (
        <div className="glass-card rounded-2xl p-8 text-center">
          <p className="text-white/55 font-light">
            Aún no has generado activos.
          </p>
          <p className="text-xs text-white/35 font-light mt-2">
            Pídele a Dona una imagen, un video o un documento y aparecerá aquí.
          </p>
        </div>
      )}

      {/* Grid de activos */}
      {load.status === "ready" && assets.length > 0 && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {assets.map((asset) => (
            <TarjetaAsset key={asset.id} asset={asset} />
          ))}
        </div>
      )}
    </section>
  );
}

function TarjetaAsset({ asset }: { asset: AssetGaleria }) {
  const [imgError, setImgError] = useState(false);
  const tipo: TipoAsset = TIPO_LABEL[asset.tipo] ? asset.tipo : "doc";
  const Icono = TIPO_ICONO[tipo];
  const esImagenConPreview =
    tipo === "image" && !!asset.url_publica && !imgError;

  return (
    <article className="glass-card rounded-2xl overflow-hidden border-white/[0.06] flex flex-col">
      {/* Preview / thumbnail */}
      <div className="relative aspect-[4/3] bg-white/[0.03] flex items-center justify-center overflow-hidden">
        {esImagenConPreview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={asset.url_publica}
            alt={asset.prompt || "Activo generado"}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <Icono className="w-10 h-10 text-white/20" />
        )}
        <span className="absolute top-2 left-2 text-[10px] px-2 py-0.5 rounded-full bg-black/40 backdrop-blur-sm border border-white/10 text-white/60 font-light">
          {TIPO_LABEL[tipo]}
        </span>
      </div>

      {/* Meta */}
      <div className="px-4 py-3 flex flex-col gap-2 flex-1">
        {asset.prompt ? (
          <p className="text-sm text-white/70 font-light leading-snug line-clamp-2">
            {asset.prompt}
          </p>
        ) : (
          <p className="text-sm text-white/40 font-light italic">
            Sin descripción
          </p>
        )}

        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <span className="text-[11px] text-white/30 font-light">
            {formatFechaIso(asset.creado)}
            {asset.modelo ? ` · ${asset.modelo}` : ""}
          </span>
          {asset.url_publica && (
            <a
              href={asset.url_publica}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-white/60 hover:text-white/90 font-light flex items-center gap-1 shrink-0 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Descargar
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
