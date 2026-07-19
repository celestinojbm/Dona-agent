# agent/automation/costos.py — Estimación de créditos por playbook (T2.1.A)

"""
Estimación determinística de créditos por playbook/acción.

T2.1.A NO descuenta créditos · solo estima. La estructura queda lista
para T2.1.D (reservas + reembolsos) cuando se conecten ejecutores
reales que sí cuestan tokens LLM o API calls externas.

Tabla de costos basada en: tokens estimados de generación, llamadas
externas, complejidad. Conservador hacia arriba para no subestimar.
"""

from __future__ import annotations

# Costo en créditos por tipo de acción.
# Default 5 si el tipo no está mapeado (mínimo seguro).
COSTO_POR_TIPO_ACCION: dict[str, int] = {
    # LOW · interno · cuesta porque usa LLM para generar
    "generar_plan_semanal": 8,
    "generar_calendario_contenido": 12,
    "generar_checklist_ventas": 5,
    "analizar_diagnostico": 6,
    "generar_idea_oferta": 6,
    # MEDIUM · prepara contenido · más LLM tokens
    "preparar_mensaje_whatsapp": 4,
    "preparar_campana_whatsapp": 15,
    "preparar_publicacion_redes": 8,
    "preparar_email_seguimiento": 5,
    "borrador_copy_oferta": 10,
    # HIGH · sumamos costo del envío real
    # enviar_correo_gmail: 0 en PR 1 — es preparación del contrato; no se
    # reserva, confirma ni libera crédito y no pasa por el pipeline de
    # execution hasta que exista la materialización (PR 2).
    "enviar_correo_gmail": 0,
    "enviar_mensaje_whatsapp": 6,
    "enviar_campana_masiva": 50,
    "publicar_red_social": 10,
    "contactar_lead": 8,
    # CRITICAL · costo elevado para reflejar gravedad operacional
    "gastar_creditos_masivo": 100,
    "borrar_datos_negocio": 0,  # gratis pero bloqueado
    "cambiar_config_cuenta": 0,
    "envio_masivo_clientes": 100,
}


def estimar_costo_accion(tipo_accion: str) -> int:
    """Estima el costo en créditos para una acción puntual.

    Default conservador: si el tipo no está en la tabla, retorna 5
    (no 0) · evita que se generen acciones 'gratis' por error.
    """
    return COSTO_POR_TIPO_ACCION.get(tipo_accion, 5)


def estimar_costo_playbook(pasos: list[dict]) -> int:
    """Suma el costo estimado de los pasos de un playbook.

    Args:
        pasos: lista de dicts con clave 'tipo_accion' (lo que entrega
               agent/automation/playbooks.py:obtener_playbook).
    """
    total = 0
    for paso in pasos:
        tipo = paso.get("tipo_accion", "")
        total += estimar_costo_accion(tipo)
    return total
