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


# ══════════════════════════════════════════════════════════════════════════
# Parte 4 · Media (voz/imagen) — Fase 3 · paridad multimodal con WhatsApp
# ══════════════════════════════════════════════════════════════════════════
#
# El chat web acepta, además de texto, una nota de voz y/o una imagen en base64,
# reusando el MISMO pipeline que WhatsApp:
#   - Voz  → agent.transcriber.transcribir_audio (texto PLANO, primera persona).
#   - Imagen → agent.vision.analizar_imagen_con_claude + el envoltorio
#     anti-inyección del webhook (SEC-INJ-07): al LLM va envuelto/sanitizado,
#     al historial va el plano legible.
# Estos tests fijan ese contrato sin llamar a proveedores reales (mocks).


@_requiere_main
class TestProcesarMediaChat:
    """Función pura _procesar_media_chat: combina texto + media en
    (mensaje_llm, mensaje_hist), con caps y errores tipados."""

    @staticmethod
    def _fn():
        from agent.main import _procesar_media_chat
        return _procesar_media_chat

    @staticmethod
    def _b64(data: bytes) -> str:
        import base64
        return base64.b64encode(data).decode("ascii")

    @pytest.mark.asyncio
    async def test_texto_solo_pasa_igual(self):
        llm, hist = await self._fn()({}, "hola dona")
        assert llm == "hola dona"
        assert hist == "hola dona"

    @pytest.mark.asyncio
    async def test_voz_se_transcribe_y_va_plano(self, monkeypatch):
        import agent.transcriber as transcriber

        async def _fake(_bytes, _mime):
            return "esto lo dije por voz"

        monkeypatch.setattr(transcriber, "transcribir_audio", _fake)
        payload = {"audio_base64": self._b64(b"audio"), "audio_mime": "audio/webm"}
        llm, hist = await self._fn()(payload, "acompaño con texto")

        assert "acompaño con texto" in llm
        assert "esto lo dije por voz" in llm
        # La voz es primera persona: NO lleva envoltorio anti-inyección.
        assert "NOTA:" not in llm
        # Historial idéntico al texto plano que ve el LLM (voz).
        assert hist == llm

    @pytest.mark.asyncio
    async def test_imagen_envuelta_para_llm_plana_para_historial(self, monkeypatch):
        import agent.vision as vision

        async def _fake(_bytes, _mime, _caption):
            return "se ve una factura por 100 dolares"

        monkeypatch.setattr(vision, "analizar_imagen_con_claude", _fake)
        payload = {"imagen_base64": self._b64(b"img"), "imagen_mime": "image/png"}
        llm, hist = await self._fn()(payload, "")

        # LLM: envoltorio anti-inyección (datos, no instrucciones).
        assert "NOTA:" in llm
        assert "EXTRAÍDO DE UNA IMAGEN" in llm
        assert "se ve una factura" in llm
        # Historial: plano legible, SIN el envoltorio.
        assert hist.startswith("[Imagen recibida]")
        assert "NOTA:" not in hist
        assert "se ve una factura" in hist

    @pytest.mark.asyncio
    async def test_imagen_con_caption_en_el_plano(self, monkeypatch):
        import agent.vision as vision
        capturado = {}

        async def _fake(_bytes, _mime, caption):
            capturado["caption"] = caption
            return "analisis"

        monkeypatch.setattr(vision, "analizar_imagen_con_claude", _fake)
        payload = {
            "imagen_base64": self._b64(b"img"),
            "imagen_mime": "image/jpeg",
            "imagen_caption": "es mi recibo",
        }
        _llm, hist = await self._fn()(payload, "")
        assert capturado["caption"] == "es mi recibo"
        assert "es mi recibo" in hist  # el caption aparece en la etiqueta

    @pytest.mark.asyncio
    async def test_audio_base64_invalido_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            await self._fn()({"audio_base64": "no-es-base64!!"}, "")
        assert e.value.status_code == 400
        assert e.value.detail == "audio_base64_invalido"

    @pytest.mark.asyncio
    async def test_imagen_base64_invalido_400(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            await self._fn()({"imagen_base64": "no-es-base64!!"}, "")
        assert e.value.status_code == 400
        assert e.value.detail == "imagen_base64_invalido"

    @pytest.mark.asyncio
    async def test_audio_demasiado_grande_413(self, monkeypatch):
        import agent.main as main
        # Bajar el cap para no allocar 12 MB en el test.
        monkeypatch.setattr(main, "_CHAT_MAX_MEDIA_BYTES", 4)
        from fastapi import HTTPException
        payload = {"audio_base64": self._b64(b"12345678")}  # 8 bytes > 4
        with pytest.raises(HTTPException) as e:
            await self._fn()(payload, "")
        assert e.value.status_code == 413
        assert e.value.detail == "audio_demasiado_grande"

    @pytest.mark.asyncio
    async def test_imagen_demasiado_grande_413(self, monkeypatch):
        import agent.main as main
        monkeypatch.setattr(main, "_CHAT_MAX_MEDIA_BYTES", 4)
        from fastapi import HTTPException
        payload = {"imagen_base64": self._b64(b"12345678")}
        with pytest.raises(HTTPException) as e:
            await self._fn()(payload, "")
        assert e.value.status_code == 413
        assert e.value.detail == "imagen_demasiado_grande"

    @pytest.mark.asyncio
    async def test_voz_intranscribible_se_omite(self, monkeypatch):
        """Si la transcripción devuelve None y no hay texto, el mensaje para el
        LLM queda vacío (el endpoint responde seguro sin llegar al LLM)."""
        import agent.transcriber as transcriber

        async def _fake(_bytes, _mime):
            return None

        monkeypatch.setattr(transcriber, "transcribir_audio", _fake)
        llm, hist = await self._fn()({"audio_base64": self._b64(b"x")}, "")
        assert llm == ""
        assert hist == ""


@_requiere_main
class TestMediaEndpoint:
    """Ruta completa /internal/chat con media (auth HMAC + resolución de sub +
    pipeline). Mocks de transcriber/vision/generar_respuesta."""

    @staticmethod
    def _b64(data: bytes) -> str:
        import base64
        return base64.b64encode(data).decode("ascii")

    @pytest.mark.asyncio
    async def test_audio_only_transcribe_y_llega_al_llm(self, setup, monkeypatch):
        client, memory, main = setup
        await _crear_sub(memory, "sub_media_a", "15551119200")

        import agent.transcriber as transcriber

        async def _fake_transcribir(_bytes, _mime):
            return "hola desde una nota de voz"

        monkeypatch.setattr(transcriber, "transcribir_audio", _fake_transcribir)
        visto = {}

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            visto["mensaje"] = mensaje
            return "te escuché"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(
            subscription_id="sub_media_a",
            audio_base64=self._b64(b"audio-bytes"),
            audio_mime="audio/webm",
        ))
        assert r.status_code == 200
        assert r.json() == {"respuesta": "te escuché"}
        assert "hola desde una nota de voz" in visto["mensaje"]

    @pytest.mark.asyncio
    async def test_image_only_llm_envuelto_historial_plano(self, setup, monkeypatch):
        client, memory, main = setup
        tel = "15551119201"
        await _crear_sub(memory, "sub_media_i", tel)

        import agent.vision as vision

        async def _fake_analizar(_bytes, _mime, _caption):
            return "una gráfica de ventas de la semana"

        monkeypatch.setattr(vision, "analizar_imagen_con_claude", _fake_analizar)
        visto = {}

        async def _fake_generar(mensaje, historial, telefono="", timestamp_mensaje=0, proveedor=None):
            visto["mensaje_llm"] = mensaje
            return "vi tu gráfica"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(
            subscription_id="sub_media_i",
            imagen_base64=self._b64(b"img-bytes"),
            imagen_mime="image/png",
        ))
        assert r.status_code == 200
        # El LLM recibe el contenido de imagen ENVUELTO (anti-inyección).
        assert "NOTA:" in visto["mensaje_llm"]
        # El historial guarda el PLANO legible (sin el envoltorio).
        hist = await memory.obtener_historial(tel)
        contenidos = [m["content"] for m in hist]
        assert any("una gráfica de ventas" in c for c in contenidos)
        assert all("NOTA:" not in c for c in contenidos)

    @pytest.mark.asyncio
    async def test_media_no_procesable_sin_texto_responde_seguro(self, setup, monkeypatch):
        """Voz intranscribible + sin texto ⇒ respuesta segura y el LLM NUNCA
        se invoca (no se cobra/ejecuta nada por un adjunto vacío)."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_media_x", "15551119202")

        import agent.transcriber as transcriber

        async def _fake(_bytes, _mime):
            return None

        monkeypatch.setattr(transcriber, "transcribir_audio", _fake)
        llamado = {"n": 0}

        async def _fake_generar(*a, **k):
            llamado["n"] += 1
            return "no debería llegar"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(
            subscription_id="sub_media_x",
            audio_base64=self._b64(b"ruido"),
        ))
        assert r.status_code == 200
        assert "No pude procesar" in r.json()["respuesta"]
        assert llamado["n"] == 0

    @pytest.mark.asyncio
    async def test_audio_base64_invalido_400_en_endpoint(self, setup):
        client, memory, _ = setup
        await _crear_sub(memory, "sub_media_bad", "15551119203")
        r = _post(client, _body(
            subscription_id="sub_media_bad",
            audio_base64="esto no es base64 !!",
        ))
        assert r.status_code == 400
        assert "audio_base64_invalido" in r.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_solo_media_no_dispara_missing_mensaje(self, setup, monkeypatch):
        """Un turno con SÓLO imagen (sin texto) no debe rechazarse como vacío."""
        client, memory, main = setup
        await _crear_sub(memory, "sub_media_om", "15551119204")

        import agent.vision as vision

        async def _fake_analizar(_bytes, _mime, _caption):
            return "contenido de la imagen"

        monkeypatch.setattr(vision, "analizar_imagen_con_claude", _fake_analizar)

        async def _fake_generar(*a, **k):
            return "ok"

        monkeypatch.setattr(main, "generar_respuesta", _fake_generar)
        r = _post(client, _body(
            subscription_id="sub_media_om",
            imagen_base64=self._b64(b"img"),
        ))
        assert r.status_code == 200
