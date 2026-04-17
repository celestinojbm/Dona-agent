# tests/test_business.py — Tests para módulo de negocio

"""
Tests para los modelos de negocio y la integración con brain.py.
Cubre: modelos, clasificación de mensajes de negocio, cotizaciones.
"""

import pytest
import json
from unittest.mock import patch

from agent.business.models import (
    PerfilNegocio, ClienteNegocio, Producto, Transaccion,
    Pedido, Seguimiento, Cotizacion, MIGRACIONES_NEGOCIO,
)
from agent.business.cotizaciones import formatear_cotizacion_texto


class TestModelos:
    """Verifica que los modelos SQLAlchemy están bien definidos."""

    def test_perfil_negocio_tablename(self):
        assert PerfilNegocio.__tablename__ == "perfil_negocio"

    def test_cliente_negocio_tablename(self):
        assert ClienteNegocio.__tablename__ == "clientes_negocio"

    def test_producto_tablename(self):
        assert Producto.__tablename__ == "productos_negocio"

    def test_transaccion_tablename(self):
        assert Transaccion.__tablename__ == "transacciones_negocio"

    def test_pedido_tablename(self):
        assert Pedido.__tablename__ == "pedidos_negocio"

    def test_seguimiento_tablename(self):
        assert Seguimiento.__tablename__ == "seguimientos_negocio"

    def test_cotizacion_tablename(self):
        assert Cotizacion.__tablename__ == "cotizaciones_negocio"

    def test_migraciones_no_vacias(self):
        assert len(MIGRACIONES_NEGOCIO) > 0

    def test_migraciones_contienen_tablas(self):
        sql_completo = " ".join(MIGRACIONES_NEGOCIO)
        assert "perfil_negocio" in sql_completo
        assert "clientes_negocio" in sql_completo
        assert "productos_negocio" in sql_completo
        assert "transacciones_negocio" in sql_completo
        assert "pedidos_negocio" in sql_completo
        assert "seguimientos_negocio" in sql_completo
        assert "cotizaciones_negocio" in sql_completo


class TestFormatearCotizacion:
    """Tests para formateo de cotizaciones como texto."""

    def test_cotizacion_basica(self):
        cot = {
            "id": 1,
            "items": [
                {"concepto": "Logo", "cantidad": 1, "precio_unitario": 3500, "subtotal": 3500},
                {"concepto": "Tarjetas", "cantidad": 1, "precio_unitario": 1200, "subtotal": 1200},
            ],
            "total": 4700,
            "cliente": "Juan",
            "vigencia_dias": 15,
            "notas": "",
        }
        texto = formatear_cotizacion_texto(cot, "Mi Estudio")
        assert "Mi Estudio" in texto
        assert "Cotización #1" in texto
        assert "Juan" in texto
        assert "Logo" in texto
        assert "4,700" in texto

    def test_cotizacion_sin_negocio(self):
        cot = {
            "id": 2,
            "items": [{"concepto": "Servicio", "cantidad": 1, "precio_unitario": 500, "subtotal": 500}],
            "total": 500,
            "cliente": "",
            "vigencia_dias": 10,
            "notas": "Pago 50% adelantado",
        }
        texto = formatear_cotizacion_texto(cot)
        assert "Cotización #2" in texto
        assert "500" in texto
        assert "Pago 50% adelantado" in texto

    def test_cotizacion_multiples_items(self):
        cot = {
            "id": 3,
            "items": [
                {"concepto": "Producto A", "cantidad": 3, "precio_unitario": 100, "subtotal": 300},
                {"concepto": "Producto B", "cantidad": 2, "precio_unitario": 250, "subtotal": 500},
            ],
            "total": 800,
            "cliente": "Ana",
            "vigencia_dias": 30,
            "notas": "",
        }
        texto = formatear_cotizacion_texto(cot)
        assert "x3" in texto
        assert "x2" in texto


class TestClasificacionNegocio:
    """Tests para que brain.py clasifique correctamente mensajes de negocio."""

    def test_venta(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("vendí 3 pasteles hoy por $1200")
        assert r is not None
        assert "registrar_venta" in r

    def test_gasto(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("gasté $600 en ingredientes")
        assert r is not None
        assert "registrar_gasto" in r

    def test_cliente(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("registra como cliente a Laura")
        assert r is not None
        assert "registrar_cliente" in r

    def test_pedido(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("me hicieron un pedido para el sábado")
        assert r is not None
        assert "crear_pedido" in r

    def test_cotizacion(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("hazme una cotización para Juan")
        assert r is not None
        assert "crear_cotizacion" in r

    def test_contenido_redes(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("genera un post para Instagram")
        assert r is not None
        assert "generar_contenido_redes" in r

    def test_finanzas(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("cómo van mis ventas este mes")
        assert r is not None
        assert "resumen_financiero" in r

    def test_productos(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("muéstrame mi catálogo de productos")
        assert r is not None
        assert "listar_productos" in r or "registrar_producto" in r

    def test_negocio_config(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("mi negocio se llama Pastelería María")
        assert r is not None
        assert "configurar_negocio" in r

    def test_seguimiento(self):
        from agent.brain import _clasificar_mensaje
        r = _clasificar_mensaje("tengo que darle seguimiento a Carlos")
        assert r is not None
        assert "crear_seguimiento" in r


class TestToolsRegistrados:
    """Verifica que todas las tools de negocio están en TOOLS."""

    def test_tools_negocio_presentes(self):
        from agent.brain import TOOLS
        nombres = {t["name"] for t in TOOLS}
        tools_negocio = {
            "registrar_cliente", "buscar_clientes", "crear_seguimiento",
            "registrar_venta", "registrar_gasto", "resumen_financiero",
            "registrar_producto", "listar_productos",
            "crear_pedido", "actualizar_pedido", "listar_pedidos",
            "crear_cotizacion", "generar_contenido_redes", "configurar_negocio",
        }
        for tool in tools_negocio:
            assert tool in nombres, f"Tool '{tool}' no encontrada en TOOLS"

    def test_tools_tienen_schema(self):
        from agent.brain import TOOLS
        for t in TOOLS:
            assert "name" in t
            assert "description" in t
            assert "input_schema" in t
            assert t["input_schema"]["type"] == "object"
