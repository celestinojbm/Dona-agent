# tests/test_memory_summary.py — Tests del resumen de memoria a largo plazo
#
# Cubre `agent.memory_summary.actualizar_resumen_si_necesario`, el orquestador
# que decide si hay suficientes mensajes nuevos para regenerar el resumen
# consolidado con el LLM. Los tests fijan el COMPORTAMIENTO ACTUAL: ramas de
# corte (sin memoria previa, <20 nuevos, sin mensajes, LLM vacío), camino feliz
# y manejo de excepciones. Todas las dependencias externas (agent.memory y
# agent.llm) se mockean — nunca se toca DB ni proveedor real.

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import agent.memory as memoria
import agent.llm as llm
import agent.memory_summary as ms


def _mensaje(id_, role, content):
    return {"id": id_, "role": role, "content": content}


@pytest.fixture
def _mocks(monkeypatch):
    """Mockea las cuatro funciones de agent.memory y completar_texto de agent.llm.

    Como `actualizar_resumen_si_necesario` hace `from agent.memory import ...`
    en tiempo de llamada, parchear los atributos del módulo fuente alcanza.
    """
    obtener_mem = AsyncMock(return_value=None)
    guardar_mem = AsyncMock(return_value=None)
    obtener_msgs = AsyncMock(return_value=[])
    obtener_ultimo = AsyncMock(return_value=0)
    completar = AsyncMock(return_value="Resumen consolidado.")

    monkeypatch.setattr(memoria, "obtener_memoria_largo_plazo", obtener_mem)
    monkeypatch.setattr(memoria, "guardar_memoria_largo_plazo", guardar_mem)
    monkeypatch.setattr(memoria, "obtener_mensajes_desde_id", obtener_msgs)
    monkeypatch.setattr(memoria, "obtener_ultimo_id_mensaje", obtener_ultimo)
    monkeypatch.setattr(llm, "completar_texto", completar)

    return {
        "obtener_mem": obtener_mem,
        "guardar_mem": guardar_mem,
        "obtener_msgs": obtener_msgs,
        "obtener_ultimo": obtener_ultimo,
        "completar": completar,
    }


class TestRamasDeCorte:
    async def test_sin_suficientes_mensajes_no_resume(self, _mocks):
        # Sin memoria previa (ultimo_id_procesado=0) y solo 19 mensajes nuevos.
        _mocks["obtener_ultimo"].return_value = 19

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is False
        _mocks["completar"].assert_not_called()
        _mocks["guardar_mem"].assert_not_called()

    async def test_exactamente_en_umbral_menos_uno_no_resume(self, _mocks):
        # El umbral es estrictamente "< MENSAJES_POR_CICLO" para NO resumir.
        _mocks["obtener_ultimo"].return_value = ms.MENSAJES_POR_CICLO - 1

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is False
        _mocks["completar"].assert_not_called()

    async def test_umbral_justo_dispara_resumen(self, _mocks):
        # Exactamente MENSAJES_POR_CICLO mensajes nuevos SÍ dispara el resumen.
        _mocks["obtener_ultimo"].return_value = ms.MENSAJES_POR_CICLO
        _mocks["obtener_msgs"].return_value = [_mensaje(20, "user", "hola")]

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is True
        _mocks["completar"].assert_awaited_once()

    async def test_sin_mensajes_recuperados_no_resume(self, _mocks):
        # Hay diff suficiente, pero obtener_mensajes_desde_id devuelve vacío.
        _mocks["obtener_ultimo"].return_value = 50
        _mocks["obtener_msgs"].return_value = []

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is False
        _mocks["completar"].assert_not_called()
        _mocks["guardar_mem"].assert_not_called()

    async def test_llm_vacio_no_guarda(self, _mocks):
        _mocks["obtener_ultimo"].return_value = 50
        _mocks["obtener_msgs"].return_value = [_mensaje(40, "user", "algo")]
        _mocks["completar"].return_value = None

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is False
        _mocks["guardar_mem"].assert_not_called()


class TestCaminoFeliz:
    async def test_resume_y_guarda_con_ultimo_id_correcto(self, _mocks):
        _mocks["obtener_ultimo"].return_value = 100
        msgs = [
            _mensaje(81, "user", "me llamo Celestino"),
            _mensaje(95, "assistant", "Encantada, Celestino"),
        ]
        _mocks["obtener_msgs"].return_value = msgs
        _mocks["completar"].return_value = "El usuario se llama Celestino."

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is True
        # Guarda con el id del ÚLTIMO mensaje recuperado, no el ultimo_id_actual.
        _mocks["guardar_mem"].assert_awaited_once()
        args = _mocks["guardar_mem"].await_args.args
        assert args[0] == "+15550001111"
        assert args[1] == "El usuario se llama Celestino."
        assert args[2] == 95

    async def test_completar_texto_pide_600_tokens(self, _mocks):
        _mocks["obtener_ultimo"].return_value = 100
        _mocks["obtener_msgs"].return_value = [_mensaje(90, "user", "x")]

        await ms.actualizar_resumen_si_necesario("+15550001111")

        kwargs = _mocks["completar"].await_args.kwargs
        assert kwargs.get("max_tokens") == 600

    async def test_usa_resumen_anterior_en_prompt(self, _mocks):
        # Con memoria previa, el resumen anterior se inyecta al prompt.
        _mocks["obtener_mem"].return_value = {
            "ultimo_mensaje_id": 80,
            "resumen_texto": "RESUMEN_PREVIO_MARCADOR",
        }
        _mocks["obtener_ultimo"].return_value = 110  # diff = 30 >= 20
        _mocks["obtener_msgs"].return_value = [_mensaje(105, "user", "nuevo dato")]

        await ms.actualizar_resumen_si_necesario("+15550001111")

        prompt_enviado = _mocks["completar"].await_args.args[0]
        assert "RESUMEN_PREVIO_MARCADOR" in prompt_enviado
        # obtener_mensajes_desde_id se llama desde el ultimo_id procesado (80).
        assert _mocks["obtener_msgs"].await_args.args[1] == 80

    async def test_trunca_mensajes_largos_a_300(self, _mocks):
        largo = "A" * 500
        _mocks["obtener_ultimo"].return_value = 100
        _mocks["obtener_msgs"].return_value = [_mensaje(90, "user", largo)]

        await ms.actualizar_resumen_si_necesario("+15550001111")

        prompt_enviado = _mocks["completar"].await_args.args[0]
        # Trunca a 300 chars y agrega la elipsis; nunca aparecen los 500.
        assert "A" * 300 in prompt_enviado
        assert "A" * 301 not in prompt_enviado
        assert "…" in prompt_enviado

    async def test_prefijos_de_rol_en_prompt(self, _mocks):
        _mocks["obtener_ultimo"].return_value = 100
        _mocks["obtener_msgs"].return_value = [
            _mensaje(90, "user", "pregunta"),
            _mensaje(91, "assistant", "respuesta"),
        ]

        await ms.actualizar_resumen_si_necesario("+15550001111")

        prompt_enviado = _mocks["completar"].await_args.args[0]
        assert "[Usuario]: pregunta" in prompt_enviado
        assert "[Dona]: respuesta" in prompt_enviado


class TestManejoDeErrores:
    async def test_excepcion_en_dependencia_devuelve_false(self, _mocks):
        _mocks["obtener_mem"].side_effect = RuntimeError("DB caída")

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        # La excepción se traga y se reporta como "no se actualizó".
        assert resultado is False

    async def test_excepcion_al_guardar_devuelve_false(self, _mocks):
        _mocks["obtener_ultimo"].return_value = 100
        _mocks["obtener_msgs"].return_value = [_mensaje(90, "user", "x")]
        _mocks["guardar_mem"].side_effect = RuntimeError("write fail")

        resultado = await ms.actualizar_resumen_si_necesario("+15550001111")

        assert resultado is False
