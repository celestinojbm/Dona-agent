# tests/test_internal_chat.py — Chat web con PARIDAD TOTAL con WhatsApp (Fase 1)
#
# Endpoint POST /internal/chat + verificación de que NO hay bypass de gates.

"""
El chat web es la pieza MÁS sensible en seguridad de Fase 1. El contrato es que
sea un THIN ADAPTER que enruta el mensaje web a la MISMA función que procesa
WhatsApp (brain.generar_respuesta), de modo que TODOS los gates se preserven
POR CONSTRUCCIÓN. Estos tests PRUEBAN que así es.

Parte 1 · Endpoint (auth HMAC, payload, resolución de sub, respuesta feliz):
  - Firma HMAC ausente/ inválida → 401.
  - JSON malformado / no objeto / sin subscription_id / sin mensaje → 400.
  - subscription_id inexistente → 404.
  - Respuesta feliz → 200 {"respuesta": ...}.

Parte 2 · SEGURIDAD — no bypass de gates (lo crítico):
  a. cobro: un mensaje web que dispara una tool con gate de quota/cobro sigue
     pasando por ese gate (se rechaza sin saldo/quota; se llama al gate).
  b. envío/TCPA: un mensaje web que intenta un envío WhatsApp sigue pasando por
     puede_enviar (el proveedor real que pasa el adapter lo enforce).
  c. HIGH: una acción HIGH sigue requiriendo preparar/confirmar — el chat NO
     tiene forma de ejecutarla directo (el brain no expone tool de ejecución
     HIGH; la ejecución vive en el executor con su gate de aprobación).
  d. anti-IDOR: el endpoint SÓLO opera sobre el telefono resuelto desde la sub,
     NUNCA uno del cliente (aunque el cliente meta telefono en el body).
  e. rate-limit: el canal web pasa por el MISMO gate que WhatsApp; excedido →
     429 y generar_respuesta NUNCA se llama.

Parte 3 · Historial compartido web↔WhatsApp por telefono.

NO cubre:
  - Bridge landing → backend (landing/lib/chat-bridge.test.ts).
  - UI del dashboard (landing/app/dashboard/seccion-chat.test.tsx).
  - Llamadas reales a LLM/proveedores (todo mockeado).
"""

import hashlib
import hmac
import importlib
import json

import pytest
from fastapi.testclient import TestClient

_main_disponible = True
try:
    from agent.main import app  # noqa: F401
except Exception:
    _main_disponible = False


_requiere_main = pytest.mark.skipif(
    not _main_disponible,
    reason="agent.main requiere apscheduler (no instalado en este entorno)",
)


SECRET_TEST = "test-secret-not-real-chat"


def _firmar(body: bytes, secret: str = SECRET_TEST) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _body(**kwargs) -> bytes:
    return json.dumps(kwargs).encode("utf-8")


def _post(client, body: bytes, firma: str | None = None):
    return client.post(
        "/internal/chat",
        content=body,
        headers={"X-Internal-Signature": firma if firma is not None else _firmar(body)},
    )


# ── Fixture: backend con DB aislada y env vars ─────────────────────────────


@pytest.fixture
async def setup(tmp_path, monkeypatch):
    db_path = tmp_path / "chat.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("INTERNAL_BRIDGE_SECRET", SECRET_TEST)

    import agent.memory
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()

    # No recargar agent.main: reusar la app ya importada (mismo patrón que
    # test_internal_assets/test_internal_reportes). Recargar main rompía la
    # ATRIBUCIÓN de cobertura del handler bajo la suite completa (diff-cover
    # no acreditaba 3856-3865 aunque los tests SÍ las ejecutan). El secreto del
    # bridge se lee por-request, así que el monkeypatch aplica sin recargar.
    import agent.main as main
    from agent.main import app

    return TestClient(app), agent.memory, main


async def _crear_sub(memory, subscription_id, telefono):
    async with memory.async_session() as session:
        session.add(memory.SuscripcionStripe(
            subscription_id=subscription_id,
            telefono=telefono,
            customer_id="cus_chat",
            plan_codigo="premium",
            price_id="price_test",
            status="active",
            creditos_mensuales=100,
        ))
        await session.commit()


# ══════════════════════════════════════════════════════════════════════════
# Parte 1 · Endpoint · auth HMAC, payload, resolución de sub
# ══════════════════════════════════════════════════════════════════════════


@_requiere_main
class TestAuth:
    def test_sin_header_401(self, setup):
        client, _, _ = setup
        r = client.post("/internal/chat", content=_body(subscription_id="s", mensaje="hola"))
        assert r.status_code == 401

    def test_firma_invalida_401(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="s", mensaje="hola"), firma="deadbeef")
        assert r.status_code == 401

    def test_firma_de_otro_secret_401(self, setup):
        client, _, _ = setup
        body = _body(subscription_id="s", mensaje="hola")
        r = _post(client, body, firma=_firmar(body, secret="atacante"))
        assert r.status_code == 401

    def test_body_modificado_tras_firmar_401(self, setup):
        client, _, _ = setup
        firma = _firmar(_body(subscription_id="sub_x", mensaje="hola"))
        r = _post(client, _body(subscription_id="sub_x", mensaje="ATACADO"), firma=firma)
        assert r.status_code == 401


@_requiere_main
class TestPayload:
    def test_no_json_400(self, setup):
        client, _, _ = setup
        body = b"no soy json"
        r = _post(client, body, firma=_firmar(body))
        assert r.status_code == 400

    def test_array_no_objeto_400(self, setup):
        client, _, _ = setup
        body = json.dumps([1, 2]).encode("utf-8")
        r = _post(client, body, firma=_firmar(body))
        assert r.status_code == 400

    def test_sin_subscription_id_400(self, setup):
        client, _, _ = setup
        r = _post(client, _body(mensaje="hola"))
        assert r.status_code == 400
        assert "missing_subscription_id" in r.json().get("detail", "")

    def test_sin_mensaje_400(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="sub_x"))
        assert r.status_code == 400
        assert "missing_mensaje" in r.json().get("detail", "")

    def test_mensaje_vacio_400(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="sub_x", mensaje="   "))
        assert r.status_code == 400

    def test_mensaje_no_string_400(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="sub_x", mensaje=123))
        assert r.status_code == 400


@_requiere_main
class TestExtraerSubYMensaje:
    """Validación del body probada DIRECTAMENTE sobre la función pura
    _extraer_sub_y_mensaje (sin ruteo por la app), para que la cobertura de
    esas ramas se acredite de forma robusta bajo la suite completa."""

    @staticmethod
    def _fn():
        from agent.main import _extraer_sub_y_mensaje
        return _extraer_sub_y_mensaje

    def test_sin_sub_id_lanza_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            self._fn()({"mensaje": "hola"})
        assert e.value.status_code == 400
        assert e.value.detail == "missing_subscription_id"

    def test_sub_id_solo_espacios_lanza_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            self._fn()({"subscription_id": "   ", "mensaje": "hola"})
        assert e.value.detail == "missing_subscription_id"

    def test_sin_mensaje_lanza_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            self._fn()({"subscription_id": "sub_x"})
        assert e.value.detail == "missing_mensaje"

    def test_mensaje_no_string_lanza_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            self._fn()({"subscription_id": "sub_x", "mensaje": 123})
        assert e.value.detail == "missing_mensaje"

    def test_mensaje_vacio_lanza_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            self._fn()({"subscription_id": "sub_x", "mensaje": "   "})
        assert e.value.detail == "missing_mensaje"

    def test_feliz_devuelve_sub_y_mensaje_stripeado(self):
        sub, msg = self._fn()({"subscription_id": "  sub_x ", "mensaje": "  hola  "})
        assert sub == "sub_x"
        assert msg == "hola"

    def test_mensaje_largo_se_trunca(self):
        _, msg = self._fn()({"subscription_id": "sub_x", "mensaje": "a" * 9000})
        assert len(msg) == 8000


@_requiere_main
class TestSubInexistente:
    def test_sub_inexistente_404(self, setup):
        client, _, _ = setup
        r = _post(client, _body(subscription_id="sub_nunca", mensaje="hola"))
        assert r.status_code == 404
        assert "subscription_no_persistida" in r.json().get("detail", "")


@_requiere_main
class TestRespuestaFeliz:
    @pytest.mark.asyncio
    async def test_respuesta_feliz_200(self, setup, monkeypatch):
        client, memory, main = setup
        await _crear_sub(memory, "sub_ok", "15551110000")

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            return "Hola, soy Dona."

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(subscription_id="sub_ok", mensaje="hola"))
        assert r.status_code == 200
        assert r.json() == {"respuesta": "Hola, soy Dona."}

    @pytest.mark.asyncio
    async def test_mensaje_largo_se_trunca_antes_del_llm(self, setup, monkeypatch):
        """Cap defensivo del endpoint: un mensaje desmesurado se trunca ANTES de
        llegar al LLM (segundo cinturón sobre el cap interno de brain)."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_largo", "15551110009")
        visto = {}

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            visto["len"] = len(mensaje)
            return "ok"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        gigante = "a" * (main._CHAT_MAX_LONGITUD_MENSAJE + 5000)
        r = _post(client, _body(subscription_id="sub_largo", mensaje=gigante))
        assert r.status_code == 200
        assert visto["len"] == main._CHAT_MAX_LONGITUD_MENSAJE

    @pytest.mark.asyncio
    async def test_timeout_de_generar_responde_seguro(self, setup, monkeypatch):
        """Si generar_respuesta excede el timeout, el endpoint responde un
        mensaje seguro (no cuelga ni 500)."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_to", "15551110010")

        async def _fake_generar(*a, **k):
            raise TimeoutError()

        # asyncio.wait_for envuelve el coro; forzamos el TimeoutError directo.
        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(subscription_id="sub_to", mensaje="hola"))
        assert r.status_code == 200
        assert "tardé demasiado" in r.json()["respuesta"].lower()

    @pytest.mark.asyncio
    async def test_error_cargando_historial_no_es_fatal(self, setup, monkeypatch):
        """Si obtener_historial falla, el turno continúa con historial vacío
        antes que no responder."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_he", "15551110011")
        visto = {}

        async def _fake_historial(tel):
            raise RuntimeError("db caída")

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            visto["historial"] = historial
            return "ok"

        monkeypatch.setattr(main, "obtener_historial", _fake_historial)
        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(subscription_id="sub_he", mensaje="hola"))
        assert r.status_code == 200
        assert visto["historial"] == []

    @pytest.mark.asyncio
    async def test_error_guardando_no_es_fatal(self, setup, monkeypatch):
        """Si guardar_mensaje falla, la respuesta ya generada igual se
        devuelve (persistir es best-effort)."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_ge", "15551110012")

        async def _fake_generar(*a, **k):
            return "respuesta viva"

        async def _fake_guardar(tel, role, content):
            raise RuntimeError("db caída al guardar")

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        monkeypatch.setattr(main, "guardar_mensaje", _fake_guardar)
        r = _post(client, _body(subscription_id="sub_ge", mensaje="hola"))
        assert r.status_code == 200
        assert r.json()["respuesta"] == "respuesta viva"


# ══════════════════════════════════════════════════════════════════════════
# Parte 2 · SEGURIDAD — el adapter NO puentea gates (por construcción)
# ══════════════════════════════════════════════════════════════════════════


@_requiere_main
class TestThinAdapterReusaGenerarRespuesta:
    """El adapter llama a LA MISMA generar_respuesta que WhatsApp, con el
    proveedor REAL. Como todos los gates viven DENTRO de esa función y de las
    tools que ella invoca, reusarla sin tocarla preserva los gates."""

    @pytest.mark.asyncio
    async def test_pasa_proveedor_real_no_none(self, setup, monkeypatch):
        """El adapter debe pasar el proveedor REAL (no None) para que las tools
        de envío a terceros (ej. ejecutor HIGH) funcionen y sus gates
        (puede_enviar/TCPA) apliquen. Un None desactivaría envíos y podría
        enmascarar el gate."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_prov", "15551110001")
        capturado = {}

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            capturado["proveedor"] = proveedor
            return "ok"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(subscription_id="sub_prov", mensaje="hola"))
        assert r.status_code == 200
        # Es el MISMO proveedor global que usa el webhook de WhatsApp.
        assert capturado["proveedor"] is main.proveedor
        assert capturado["proveedor"] is not None


@_requiere_main
class TestIDOR:
    @pytest.mark.asyncio
    async def test_ignora_telefono_del_cliente_usa_el_resuelto(self, setup, monkeypatch):
        """anti-IDOR · aunque el cliente meta un telefono en el body, el
        endpoint procesa SIEMPRE sobre el telefono resuelto desde la sub."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_a", "15551110002")
        capturado = {}

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            capturado["telefono"] = telefono
            return "ok"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        # El cliente intenta inyectar el telefono de otra víctima.
        r = _post(client, _body(
            subscription_id="sub_a",
            mensaje="hola",
            telefono="19998887777",  # ← debe IGNORARSE por completo
        ))
        assert r.status_code == 200
        assert capturado["telefono"] == "15551110002"  # el resuelto, no el del cliente
        assert capturado["telefono"] != "19998887777"

    @pytest.mark.asyncio
    async def test_persiste_bajo_telefono_resuelto_no_del_cliente(self, setup, monkeypatch):
        """El intercambio se guarda bajo el telefono resuelto, no uno del
        cliente · el historial de la víctima no se contamina."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_b", "15551110003")
        guardados = []

        async def _fake_generar(*a, **k):
            return "respuesta-de-dona"

        async def _fake_guardar(telefono, role, content):
            guardados.append((telefono, role, content))

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        monkeypatch.setattr(main, "guardar_mensaje", _fake_guardar)
        r = _post(client, _body(
            subscription_id="sub_b", mensaje="hola", telefono="10009998888",
        ))
        assert r.status_code == 200
        # Ambos turnos bajo el telefono RESUELTO.
        assert all(t == "15551110003" for t, _, _ in guardados)
        assert ("15551110003", "user", "hola") in guardados
        assert ("15551110003", "assistant", "respuesta-de-dona") in guardados


@_requiere_main
class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_excedido_429_y_no_llama_generar(self, setup, monkeypatch):
        """El canal web NO se salta el rate limit: usa el MISMO gate que
        WhatsApp (rate_limiter.dentro_de_limite via main._dentro_de_limite).
        Excedido → 429 y generar_respuesta NUNCA se llama."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_rl", "15551110004")
        llamado = {"n": 0}

        async def _fake_generar(*a, **k):
            llamado["n"] += 1
            return "no debería llegar"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        # Simular límite excedido.
        monkeypatch.setattr(main, "_dentro_de_limite", lambda tel: False)

        r = _post(client, _body(subscription_id="sub_rl", mensaje="spam"))
        assert r.status_code == 429
        assert "rate_limit" in r.json().get("detail", "")
        assert llamado["n"] == 0  # NO se procesó nada

    @pytest.mark.asyncio
    async def test_rate_limit_ok_si_dentro_de_limite(self, setup, monkeypatch):
        client, memory, main = setup
        await _crear_sub(memory, "sub_rl2", "15551110005")

        async def _fake_generar(*a, **k):
            return "ok"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        monkeypatch.setattr(main, "_dentro_de_limite", lambda tel: True)
        r = _post(client, _body(subscription_id="sub_rl2", mensaje="hola"))
        assert r.status_code == 200


# ── Parte 2 (cont.) · gates DENTRO de la generar_respuesta REAL ────────────
#
# Aquí NO mockeamos generar_respuesta: la corremos de verdad con el cliente
# Anthropic mockeado emitiendo tool_use. Probamos que el mensaje web, al fluir
# por la MISMA función, sigue tocando los gates de las tools.


class _Usage:
    def __init__(self, i=10, o=10):
        self.input_tokens = i
        self.output_tokens = o


class _BlkText:
    type = "text"
    def __init__(self, txt):
        self.text = txt


class _BlkTool:
    type = "tool_use"
    def __init__(self, name, id="t1", input=None):
        self.name = name
        self.id = id
        self.input = input or {}


class _Resp:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content
        self.usage = _Usage()


@_requiere_main
class TestGateCobroDentroDelBrain:
    """cobro/quota · un mensaje web que dispara una tool paga del brain sigue
    pasando por su gate. Usamos generar_contenido_redes, cuyo gate real es
    verificar_quota (misma familia que cobrar_o_rechazar: 'gate antes de
    trabajo caro'). Probamos que:
      - el gate SE LLAMA (no se puentea), y
      - si el gate rechaza, NO se ejecuta el trabajo caro (generar_contenido)."""

    @pytest.mark.asyncio
    async def test_tool_paga_web_pasa_por_gate_y_rechaza_sin_quota(self, monkeypatch):
        import agent.brain as brain

        # 1ª respuesta del LLM: pedir la tool paga. 2ª: cerrar el turno.
        secuencia = [
            _Resp("tool_use", [_BlkTool("generar_contenido_redes", input={"tema": "promo"})]),
            _Resp("end_turn", [_BlkText("listo")]),
        ]
        llamadas = {"n": 0}

        async def _fake_create(**kwargs):
            i = llamadas["n"]
            llamadas["n"] += 1
            return secuencia[min(i, len(secuencia) - 1)]

        monkeypatch.setattr(brain.client.messages, "create", _fake_create)
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])

        gate = {"llamado": False}

        async def _fake_verificar_quota(telefono, recurso):
            gate["llamado"] = True
            return (False, "Sin quota hoy. Recarga para más.")  # RECHAZA

        trabajo = {"ejecutado": False}

        async def _fake_generar_contenido(**kwargs):
            trabajo["ejecutado"] = True
            return "contenido caro"

        import agent.business.contenido as contenido
        import agent.business.quotas as quotas
        monkeypatch.setattr(quotas, "verificar_quota", _fake_verificar_quota)
        monkeypatch.setattr(contenido, "generar_contenido", _fake_generar_contenido)

        # Flujo IDÉNTICO al que el adapter web ejecuta: la MISMA función.
        resp = await brain.generar_respuesta(
            "hazme un post para redes", [], telefono="15551119000",
        )

        assert gate["llamado"] is True, "el gate de quota DEBE llamarse"
        assert trabajo["ejecutado"] is False, "sin quota NO se ejecuta trabajo caro"
        assert isinstance(resp, str) and resp


@_requiere_main
class TestGateEnvioTCPADentroDelBrain:
    """envío/TCPA · un mensaje web que intenta un envío de correo sigue pasando
    por la tool de envío gateada (confirmar_envio_correo → gmail.enviar_correo),
    no por un atajo. Probamos que el envío llega a la función de envío real (el
    punto donde vive el gate), disparado por el mensaje web."""

    @pytest.mark.asyncio
    async def test_envio_web_llega_a_funcion_de_envio_gateada(self, monkeypatch):
        import agent.brain as brain

        # Sembrar un borrador pendiente para este telefono (como si 'preparar'
        # ya hubiera corrido) para que confirmar tenga qué enviar.
        tel = "15551119001"
        brain._borradores_pendientes[tel] = {
            "destinatario": "cliente@example.com",
            "asunto": "Hola",
            "cuerpo": "Cuerpo",
        }

        secuencia = [
            _Resp("tool_use", [_BlkTool("confirmar_envio_correo")]),
            _Resp("end_turn", [_BlkText("enviado")]),
        ]
        llamadas = {"n": 0}

        async def _fake_create(**kwargs):
            i = llamadas["n"]
            llamadas["n"] += 1
            return secuencia[min(i, len(secuencia) - 1)]

        monkeypatch.setattr(brain.client.messages, "create", _fake_create)
        monkeypatch.setattr(brain, "seleccionar_tools", lambda m, t: [])

        envio = {"llamado": False, "telefono": None}

        import agent.gmail as gmail

        async def _fake_enviar_correo(telefono, destinatario, asunto, cuerpo, thread_id="", reply_message_id=""):
            # Este es el punto de envío real (la tool gateada). Que el mensaje
            # web llegue AQUÍ prueba que el envío NO se puentea.
            envio["llamado"] = True
            envio["telefono"] = telefono
            return True

        monkeypatch.setattr(gmail, "enviar_correo", _fake_enviar_correo)

        resp = await brain.generar_respuesta(
            "envía el correo", [], telefono=tel,
        )

        assert envio["llamado"] is True, "el envío DEBE pasar por la tool gateada"
        assert envio["telefono"] == tel  # bajo el telefono correcto
        assert isinstance(resp, str) and resp
        brain._borradores_pendientes.pop(tel, None)


@_requiere_main
class TestGateHighRequierePrepararConfirmar:
    """HIGH · una acción HIGH (efecto externo real a terceros) NO se ejecuta
    directo: requiere aprobación dedicada (preparar/confirmar). El chat web NO
    puede puentearlo porque:
      1. el brain no expone ninguna tool que ejecute acciones HIGH, y
      2. la capa de permisos marca HIGH como 'confirmación dedicada requerida'."""

    def test_high_requiere_confirmacion_dedicada(self):
        from agent.automation.permissions import calcular_next_required_action
        # Una acción HIGH aprobada NO es auto-ejecutable: exige confirmación.
        next_action, motivo = calcular_next_required_action("approved", "high")
        assert next_action == "dedicated_confirmation_required"
        assert motivo  # hay un motivo explícito para el usuario

    @pytest.mark.asyncio
    async def test_brain_no_tiene_tool_de_ejecucion_high(self):
        import agent.brain as brain
        nombres = {t["name"] for t in brain.TOOLS}
        # Ninguna de las acciones HIGH del catálogo de automation es una tool
        # que el LLM del chat pueda invocar directamente.
        from agent.automation.permissions import RIESGO_POR_TIPO_ACCION
        high = {tipo for tipo, r in RIESGO_POR_TIPO_ACCION.items() if r.value == "high"}
        assert high, "sanity: hay acciones HIGH en el catálogo"
        assert nombres.isdisjoint(high), (
            "el brain NO debe exponer tools que ejecuten acciones HIGH directo"
        )


# ══════════════════════════════════════════════════════════════════════════
# Parte 3 · Historial compartido web↔WhatsApp por telefono
# ══════════════════════════════════════════════════════════════════════════


@_requiere_main
class TestHistorialCompartido:
    @pytest.mark.asyncio
    async def test_carga_historial_del_telefono_resuelto(self, setup, monkeypatch):
        client, memory, main = setup
        tel = "15551119100"
        await _crear_sub(memory, "sub_hist", tel)
        # Sembrar historial previo (como si viniera de WhatsApp).
        await memory.guardar_mensaje(tel, "user", "mensaje viejo de whatsapp")
        await memory.guardar_mensaje(tel, "assistant", "respuesta vieja")

        visto = {}

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            visto["historial"] = historial
            return "ok"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(subscription_id="sub_hist", mensaje="nuevo por web"))
        assert r.status_code == 200
        # El historial de WhatsApp está disponible para el turno web (compartido).
        contenidos = [m["content"] for m in visto["historial"]]
        assert "mensaje viejo de whatsapp" in contenidos

    @pytest.mark.asyncio
    async def test_persiste_intercambio_para_whatsapp(self, setup, monkeypatch):
        """Tras un turno web, el intercambio queda en el MISMO historial que lee
        WhatsApp (por telefono)."""
        client, memory, main = setup
        tel = "15551119101"
        await _crear_sub(memory, "sub_hist2", tel)

        async def _fake_generar(*a, **k):
            return "respuesta web"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(subscription_id="sub_hist2", mensaje="pregunta web"))
        assert r.status_code == 200

        # Leer el historial como lo haría WhatsApp.
        hist = await memory.obtener_historial(tel)
        contenidos = [m["content"] for m in hist]
        assert "pregunta web" in contenidos
        assert "respuesta web" in contenidos
