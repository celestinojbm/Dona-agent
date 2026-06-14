# agent/creativos/pdf.py — Generación de documentos PDF (factura/presupuesto/recibo)

"""
Genera documentos tipo **factura**, **presupuesto** y **recibo** en PDF.

Diseño (mismo patrón que imagen.py / voz.py / bg_remove.py):
  - `generar_pdf()` es la capa pura: recibe datos estructurados, retorna
    `(pdf_bytes, meta)`. Usa reportlab si está disponible; si no, retorna
    un PDF stub mínimo para que dev/tests sigan funcionando sin la lib.
  - `preparar_documento()` / `confirmar_documento()` implementan el flujo
    de 2 pasos (naming LITERAL según CLAUDE.md §3.1).
  - La extracción de datos desde texto libre la hace el LLM (Claude Haiku)
    vía `extraer_datos_documento()` — devuelve JSON estructurado.
  - Costo plano: `COSTO_DOCUMENTO` créditos (incluye LLM + PDF).

Tipos soportados:
  - **factura**  — invoice, con # y fecha de emisión/vencimiento
  - **presupuesto** — quote, con vigencia en días (default 15)
  - **recibo**  — receipt, "pagado", con método
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("dona")


# ── Config ──────────────────────────────────────────────────────────────────

PENDIENTE_TTL_MIN = int(os.getenv("DOC_PENDIENTE_TTL_MIN", "15"))

TIPOS_VALIDOS = ("factura", "presupuesto", "recibo")

# Titulares y leyendas por tipo (ES)
_TITULOS = {
    "factura": "FACTURA",
    "presupuesto": "PRESUPUESTO",
    "recibo": "RECIBO",
}

_LEYENDAS_COLA = {
    "factura": "Gracias por tu compra.",
    "presupuesto": "Presupuesto sujeto a cambios sin previo aviso.",
    "recibo": "Este documento certifica el pago recibido.",
}


class PDFError(Exception):
    """Error genérico del provider (falta lib, datos mal formados, etc.)."""


# ── Stub PDF (para tests / dev sin reportlab) ───────────────────────────────

# PDF mínimo válido (~500 bytes) con el texto "Dona — documento stub".
# Útil para probar el flow sin instalar reportlab.
_STUB_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    b"4 0 obj\n<< /Length 60 >>\nstream\n"
    b"BT /F1 16 Tf 72 720 Td (Dona - documento stub) Tj ET\n"
    b"endstream\nendobj\n"
    b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"xref\n0 6\n0000000000 65535 f\n"
    b"0000000010 00000 n\n0000000060 00000 n\n0000000110 00000 n\n"
    b"0000000220 00000 n\n0000000330 00000 n\n"
    b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n400\n%%EOF\n"
)


# ── Capa pura: PDF con reportlab ────────────────────────────────────────────

def _fmt_money(valor: float, moneda: str = "USD") -> str:
    simbolo = {"USD": "$", "MXN": "$", "EUR": "€", "GBP": "£"}.get(moneda.upper(), "")
    try:
        return f"{simbolo}{float(valor):,.2f}"
    except (TypeError, ValueError):
        return f"{simbolo}0.00"


def _normalizar_items(items: list[dict]) -> list[dict]:
    """Normaliza items y calcula subtotales. Filtra filas vacías."""
    out = []
    for it in items or []:
        desc = str(it.get("descripcion") or it.get("concepto") or "").strip()
        if not desc:
            continue
        cant = it.get("cantidad", 1)
        try:
            cant = float(cant)
        except (TypeError, ValueError):
            cant = 1.0
        precio = it.get("precio_unit", it.get("precio_unitario", it.get("precio", 0)))
        try:
            precio = float(precio)
        except (TypeError, ValueError):
            precio = 0.0
        subtotal = round(cant * precio, 2)
        out.append({
            "descripcion": desc[:200],
            "cantidad": cant,
            "precio_unit": precio,
            "subtotal": subtotal,
        })
    return out


def _totales(items: list[dict], impuesto_pct: float = 0.0) -> tuple[float, float, float]:
    subtotal = round(sum(i["subtotal"] for i in items), 2)
    impuesto = round(subtotal * (impuesto_pct / 100.0), 2) if impuesto_pct else 0.0
    total = round(subtotal + impuesto, 2)
    return subtotal, impuesto, total


def _folio(tipo: str) -> str:
    """Folio basado en timestamp — simple, no requiere DB."""
    prefijo = {"factura": "F", "presupuesto": "P", "recibo": "R"}.get(tipo, "D")
    return f"{prefijo}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"


async def generar_pdf(
    tipo: str,
    datos: dict,
    emisor: dict | None = None,
) -> tuple[bytes, dict]:
    """
    Genera el PDF. `datos` esperado:
      - cliente (dict): {nombre, email?, telefono?, direccion?}
      - items (list): [{descripcion, cantidad, precio_unit}]
      - impuesto_pct (float, opcional)
      - notas (str, opcional)
      - moneda (str, opcional — default del emisor o "USD")
      - vigencia_dias (int, sólo presupuesto — default 15)
      - metodo_pago (str, sólo recibo — "efectivo"/"transferencia"/...)

    `emisor`: {nombre_negocio, moneda, ...} — si None, valores genéricos.

    Retorna (pdf_bytes, meta). Si reportlab no está instalado, retorna STUB.
    """
    tipo = (tipo or "factura").lower()
    if tipo not in TIPOS_VALIDOS:
        raise PDFError(f"tipo inválido: {tipo}")

    emisor = emisor or {}
    nombre_negocio = emisor.get("nombre_negocio") or "Mi Negocio"
    moneda = (datos.get("moneda") or emisor.get("moneda") or "USD").upper()

    items = _normalizar_items(datos.get("items") or [])
    if not items:
        raise PDFError("documento sin items")

    impuesto_pct = float(datos.get("impuesto_pct") or 0.0)
    subtotal, impuesto, total = _totales(items, impuesto_pct)
    folio = datos.get("folio") or _folio(tipo)

    # Intento reportlab; si no está, stub.
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import LETTER  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        logger.warning("[PDF] reportlab no instalado — retornando stub PDF")
        return _STUB_PDF, {
            "modelo": "placeholder",
            "tipo": tipo,
            "mime_type": "application/pdf",
            "bytes_size": len(_STUB_PDF),
            "placeholder": True,
            "folio": folio,
            "total": total,
            "moneda": moneda,
        }

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title=f"{_TITULOS[tipo]} {folio}",
    )
    styles = getSampleStyleSheet()
    st_h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#333333"), spaceAfter=4)
    st_normal = ParagraphStyle("n", parent=styles["BodyText"], fontSize=10, textColor=colors.HexColor("#222222"))
    st_small = ParagraphStyle("s", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#555555"))
    st_right = ParagraphStyle("r", parent=st_normal, alignment=TA_RIGHT)
    st_right_b = ParagraphStyle("rb", parent=st_right, fontName="Helvetica-Bold")

    story: list[Any] = []

    # Encabezado: nombre negocio ↔ tipo + folio
    fecha_str = datetime.utcnow().strftime("%Y-%m-%d")
    header_tbl = Table(
        [[
            Paragraph(f"<b>{nombre_negocio}</b>", st_h2),
            Paragraph(f"<b>{_TITULOS[tipo]}</b><br/><font size=9>#{folio}</font><br/><font size=9>{fecha_str}</font>", st_right_b),
        ]],
        colWidths=[3.6 * inch, 3.6 * inch],
    )
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 10))

    # Línea divisoria sutil (tabla vacía con borde superior)
    divider = Table([[""]], colWidths=[7.2 * inch], rowHeights=[1])
    divider.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#CCCCCC"))]))
    story.append(divider)
    story.append(Spacer(1, 10))

    # Cliente
    cli = datos.get("cliente") or {}
    cli_nombre = (cli.get("nombre") or "").strip() or "Cliente"
    cli_lineas = [f"<b>Para:</b> {cli_nombre}"]
    if cli.get("email"):
        cli_lineas.append(str(cli["email"]))
    if cli.get("telefono"):
        cli_lineas.append(str(cli["telefono"]))
    if cli.get("direccion"):
        cli_lineas.append(str(cli["direccion"]))
    story.append(Paragraph("<br/>".join(cli_lineas), st_normal))

    # Datos específicos por tipo
    extras = []
    if tipo == "presupuesto":
        vig = int(datos.get("vigencia_dias") or 15)
        hasta = (datetime.utcnow() + timedelta(days=vig)).strftime("%Y-%m-%d")
        extras.append(f"<b>Válido hasta:</b> {hasta} ({vig} días)")
    elif tipo == "factura":
        venc = datos.get("fecha_vencimiento")
        if not venc:
            venc = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
        extras.append(f"<b>Vencimiento:</b> {venc}")
    elif tipo == "recibo":
        metodo = (datos.get("metodo_pago") or "efectivo").strip()
        extras.append(f"<b>Método de pago:</b> {metodo}")
        extras.append("<b>Estado:</b> PAGADO")
    if extras:
        story.append(Spacer(1, 6))
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(extras), st_small))

    story.append(Spacer(1, 14))

    # Tabla de items
    data_items: list[list[Any]] = [[
        Paragraph("<b>Descripción</b>", st_normal),
        Paragraph("<b>Cant.</b>", st_right_b),
        Paragraph("<b>Precio</b>", st_right_b),
        Paragraph("<b>Subtotal</b>", st_right_b),
    ]]
    for it in items:
        data_items.append([
            Paragraph(it["descripcion"], st_normal),
            Paragraph(f"{it['cantidad']:g}", st_right),
            Paragraph(_fmt_money(it["precio_unit"], moneda), st_right),
            Paragraph(_fmt_money(it["subtotal"], moneda), st_right),
        ])
    tabla = Table(data_items, colWidths=[3.8 * inch, 0.7 * inch, 1.3 * inch, 1.4 * inch])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#AAAAAA")),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 10))

    # Totales
    total_rows = [[Paragraph("Subtotal", st_right), Paragraph(_fmt_money(subtotal, moneda), st_right)]]
    if impuesto_pct:
        total_rows.append([
            Paragraph(f"Impuesto ({impuesto_pct:g}%)", st_right),
            Paragraph(_fmt_money(impuesto, moneda), st_right),
        ])
    total_rows.append([
        Paragraph("<b>TOTAL</b>", st_right_b),
        Paragraph(f"<b>{_fmt_money(total, moneda)}</b>", st_right_b),
    ])
    tabla_tot = Table(total_rows, colWidths=[5.8 * inch, 1.4 * inch])
    tabla_tot.setStyle(TableStyle([
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#AAAAAA")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabla_tot)

    # Notas
    notas = (datos.get("notas") or "").strip()
    if notas:
        story.append(Spacer(1, 14))
        story.append(Paragraph(f"<b>Notas</b><br/>{notas}", st_small))

    # Pie
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        f"<font color='#888888'>{_LEYENDAS_COLA.get(tipo, '')}</font>", st_small,
    ))

    try:
        doc.build(story)
    except Exception as e:
        raise PDFError(f"reportlab falló al construir PDF: {e}")

    pdf_bytes = buf.getvalue()
    buf.close()

    return pdf_bytes, {
        "modelo": "reportlab",
        "tipo": tipo,
        "mime_type": "application/pdf",
        "bytes_size": len(pdf_bytes),
        "placeholder": False,
        "folio": folio,
        "total": total,
        "subtotal": subtotal,
        "impuesto": impuesto,
        "moneda": moneda,
    }


# ── Extracción de datos desde texto libre (LLM) ─────────────────────────────

_SYSTEM_EXTRACCION = (
    "Eres un asistente que extrae datos estructurados de un pedido para "
    "generar un documento ({tipo}). Responde SOLO JSON válido, sin texto "
    "adicional ni bloques de código.\n\n"
    "Esquema:\n"
    "{{\n"
    '  "cliente": {{"nombre": str, "email": str?, "telefono": str?, "direccion": str?}},\n'
    '  "items": [{{"descripcion": str, "cantidad": number, "precio_unit": number}}],\n'
    '  "moneda": "USD"|"MXN"|"EUR"|str?,\n'
    '  "impuesto_pct": number?,\n'
    '  "notas": str?,\n'
    '  "vigencia_dias": number?,\n'
    '  "metodo_pago": str?\n'
    "}}\n\n"
    "Reglas:\n"
    "- Si la cantidad no está explícita, usa 1.\n"
    "- Los montos deben ser números (sin signo de moneda).\n"
    "- Si el precio total de una línea es claro pero no el unitario, "
    "  divide entre la cantidad.\n"
    "- Devuelve al menos un item en `items`.\n"
    "- No inventes datos: si faltan campos opcionales, omítelos."
)


async def extraer_datos_documento(tipo: str, texto: str) -> dict:
    """
    Usa el LLM para sacar datos estructurados del texto libre del usuario.
    Retorna dict normalizado. Si el LLM falla, retorna estructura mínima
    con el texto como única línea (para que el usuario pueda editar).
    """
    from agent.llm import completar_con_sistema

    system = _SYSTEM_EXTRACCION.format(tipo=tipo)
    respuesta = await completar_con_sistema(system, texto, max_tokens=600)

    if not respuesta:
        logger.warning("[PDF] LLM no respondió — usando fallback mínimo")
        return {
            "cliente": {"nombre": ""},
            "items": [{"descripcion": texto.strip()[:200] or "Servicio", "cantidad": 1, "precio_unit": 0}],
        }

    # Intento parsear JSON. Si viene con ```json fences, los quito.
    txt = respuesta.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").strip()
        if txt.lower().startswith("json"):
            txt = txt[4:].strip()
    try:
        datos = json.loads(txt)
    except json.JSONDecodeError:
        # Heurística: extraer el primer bloque {...}
        a = txt.find("{")
        b = txt.rfind("}")
        if a >= 0 and b > a:
            try:
                datos = json.loads(txt[a:b + 1])
            except json.JSONDecodeError as e:
                logger.warning(f"[PDF] No pude parsear JSON del LLM: {e}")
                datos = {}
        else:
            datos = {}

    if not isinstance(datos, dict):
        datos = {}

    # Sanitizar estructura
    cli = datos.get("cliente") or {}
    if not isinstance(cli, dict):
        cli = {"nombre": str(cli)}
    items = datos.get("items")
    if not isinstance(items, list) or not items:
        items = [{"descripcion": texto.strip()[:200] or "Servicio", "cantidad": 1, "precio_unit": 0}]

    return {
        "cliente": {
            "nombre": str(cli.get("nombre") or "").strip()[:200],
            "email": str(cli.get("email") or "").strip()[:200],
            "telefono": str(cli.get("telefono") or "").strip()[:50],
            "direccion": str(cli.get("direccion") or "").strip()[:300],
        },
        "items": items,
        "moneda": (datos.get("moneda") or "").strip().upper()[:10],
        "impuesto_pct": datos.get("impuesto_pct") or 0,
        "notas": str(datos.get("notas") or "").strip()[:1000],
        "vigencia_dias": datos.get("vigencia_dias") or 15,
        "metodo_pago": str(datos.get("metodo_pago") or "").strip()[:50],
    }


async def obtener_emisor(telefono: str) -> dict:
    """
    Lee `PerfilNegocio` del usuario para usar como emisor del documento.
    Si no hay perfil, retorna valores genéricos.
    """
    try:
        from sqlalchemy import select

        from agent.business.models import PerfilNegocio
        from agent.memory import async_session

        async with async_session() as session:
            row = (await session.execute(
                select(PerfilNegocio).where(PerfilNegocio.telefono == telefono)
            )).scalar_one_or_none()
            if row:
                return {
                    "nombre_negocio": row.nombre_negocio or "Mi Negocio",
                    "moneda": (row.moneda or "USD").upper(),
                    "industria": row.industria or "general",
                }
    except Exception as e:
        logger.debug(f"[PDF] No pude leer PerfilNegocio: {e}")
    return {"nombre_negocio": "Mi Negocio", "moneda": "USD"}


# ── Pendientes (preparar → confirmar) ───────────────────────────────────────

@dataclass
class DocumentoPendiente:
    telefono: str
    tipo: str
    datos: dict
    emisor: dict
    costo_creditos: int
    creado: datetime = field(default_factory=datetime.utcnow)

    def expirado(self) -> bool:
        return datetime.utcnow() - self.creado > timedelta(minutes=PENDIENTE_TTL_MIN)


_PENDIENTES: dict[str, DocumentoPendiente] = {}


def obtener_pendiente(telefono: str) -> DocumentoPendiente | None:
    p = _PENDIENTES.get(telefono)
    if p is None:
        return None
    if p.expirado():
        _PENDIENTES.pop(telefono, None)
        return None
    return p


# ── API 2 pasos ─────────────────────────────────────────────────────────────

async def preparar_documento(
    telefono: str,
    tipo: str,
    cuerpo: str,
) -> dict:
    """
    Extrae datos del `cuerpo` (texto libre), guarda pendiente y retorna preview.
    NO cobra, NO genera el PDF. Se guarda datos normalizados + emisor.
    """
    from agent.billing import COSTO_DOCUMENTO, obtener_saldo
    from agent.creativos.pendientes import cancelar_otros_pendientes

    tipo = (tipo or "factura").lower()
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: {tipo}")

    cuerpo = (cuerpo or "").strip()
    if not cuerpo:
        raise ValueError("cuerpo vacío")

    # Un solo pendiente activo por teléfono — si había otro, lo reemplazamos.
    reemplazo = cancelar_otros_pendientes(telefono, excepto="documento")

    datos = await extraer_datos_documento(tipo, cuerpo)
    emisor = await obtener_emisor(telefono)

    # Usar moneda del emisor si el LLM no devolvió
    if not datos.get("moneda"):
        datos["moneda"] = emisor.get("moneda", "USD")

    # Normalizar items para que el preview muestre subtotales correctos
    items_norm = _normalizar_items(datos.get("items") or [])
    datos["items"] = items_norm
    subtotal, impuesto, total = _totales(items_norm, float(datos.get("impuesto_pct") or 0))

    saldo = await obtener_saldo(telefono)
    costo = COSTO_DOCUMENTO

    pendiente = DocumentoPendiente(
        telefono=telefono,
        tipo=tipo,
        datos=datos,
        emisor=emisor,
        costo_creditos=costo,
    )
    _PENDIENTES[telefono] = pendiente

    return {
        "tipo": tipo,
        "cliente": datos["cliente"]["nombre"] or "(sin cliente)",
        "items_count": len(items_norm),
        "items": items_norm,
        "subtotal": subtotal,
        "impuesto": impuesto,
        "total": total,
        "moneda": datos.get("moneda", "USD"),
        "nombre_negocio": emisor.get("nombre_negocio", "Mi Negocio"),
        "costo_creditos": costo,
        "saldo_actual": saldo,
        "alcanza": saldo >= costo,
        "ttl_min": PENDIENTE_TTL_MIN,
        "reemplazo": reemplazo,
    }


async def confirmar_documento(telefono: str) -> dict:
    """Cobra y encola job `gen_documento`. Retorna estado."""
    pendiente = obtener_pendiente(telefono)
    if pendiente is None:
        return {"estado": "sin_pendiente"}

    from agent.billing import cobrar_o_rechazar
    from agent.jobs import encolar

    ok, err = await cobrar_o_rechazar(
        telefono,
        pendiente.costo_creditos,
        f"gen_documento:{pendiente.tipo} ({pendiente.costo_creditos}cr)",
    )
    if not ok:
        return {"estado": "saldo_insuficiente", "mensaje": err}

    job_id = await encolar(
        "gen_documento",
        telefono,
        {
            "tipo": pendiente.tipo,
            "datos": pendiente.datos,
            "emisor": pendiente.emisor,
            "costo_creditos": pendiente.costo_creditos,
        },
    )
    _PENDIENTES.pop(telefono, None)
    return {"estado": "ok", "job_id": job_id, "tipo": pendiente.tipo}


def cancelar_documento(telefono: str) -> bool:
    return _PENDIENTES.pop(telefono, None) is not None
