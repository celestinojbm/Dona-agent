# tests/test_learning_patrones.py — cobertura de agent/learning.py

"""
Fija el comportamiento ACTUAL del motor de aprendizaje continuo de Dona.

Cubre las funciones de `agent.learning` que hoy no tenían test dedicado:

  * registrar_interaccion   — persistencia del evento + conversión UTC→local
                              vía offset, y captura silenciosa de errores.
  * analizar_patrones       — cómputo de los 5 patrones (horas/días pico,
                              días de estrés, preferencia de brevedad,
                              recordatorios), umbral mínimo de eventos,
                              persistencia del perfil y ramas None.
  * _generar_perfil_texto   — wrapper del LLM (éxito y excepción → None).
  * actualizar_perfiles_todos — job semanal: sin usuarios, con usuarios,
                              aislamiento de errores por usuario y captura
                              del error de nivel superior.

El LLM (`agent.llm.completar_texto`) se mockea SIEMPRE — nunca llamada real.
La DB es SQLite aislada por test (recarga de `agent.memory` tras fijar
DATABASE_URL), siguiendo el patrón de CLAUDE.md §5. Estos tests cubren el
comportamiento existente; no cambian la lógica de producción.
"""

import importlib
from datetime import datetime, timedelta

import pytest

import agent.learning as learning
import agent.memory


# --------------------------------------------------------------------------- #
# Fixture de DB aislada
# --------------------------------------------------------------------------- #
@pytest.fixture
async def db(tmp_path, monkeypatch):
    """SQLite por test · recarga agent.memory para que tome DATABASE_URL.

    learning.py importa de agent.memory de forma perezosa dentro de cada
    función, así que recargar solo agent.memory basta: las llamadas toman el
    módulo recargado en tiempo de ejecución. No se recarga learning.
    """
    db_path = tmp_path / "learning.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    importlib.reload(agent.memory)
    await agent.memory.inicializar_db()
    return agent.memory


# --------------------------------------------------------------------------- #
# Helpers de mock del LLM y de siembra de eventos
# --------------------------------------------------------------------------- #
def _mock_perfil_texto(monkeypatch, respuesta):
    """Captura el `datos` crudo pasado a _generar_perfil_texto y devuelve
    `respuesta`. Permite verificar el cómputo de patrones sin llamar al LLM."""
    capturado = {}

    async def fake(datos):
        capturado["datos"] = datos
        return respuesta

    monkeypatch.setattr(learning, "_generar_perfil_texto", fake)
    return capturado


async def _sembrar(mem, telefono, tipo, *, hora=9, dia=0, longitud=None, n=1):
    """Inserta `n` eventos de comportamiento idénticos."""
    metadata = {"longitud": longitud} if longitud is not None else {}
    for _ in range(n):
        await mem.guardar_evento_comportamiento(telefono, tipo, hora, dia, metadata)


# =========================================================================== #
# registrar_interaccion
# =========================================================================== #
class TestRegistrarInteraccion:
    async def test_persiste_evento_con_tipo_y_metadata(self, db):
        await learning.registrar_interaccion(
            "5551", "message_sent", metadata={"longitud": 42}
        )
        eventos = await db.obtener_eventos_comportamiento("5551")
        assert len(eventos) == 1
        assert eventos[0]["tipo"] == "message_sent"
        assert eventos[0]["metadata"]["longitud"] == 42

    async def test_metadata_none_se_guarda_como_dict_vacio(self, db):
        await learning.registrar_interaccion("5552", "reminder_created")
        eventos = await db.obtener_eventos_comportamiento("5552")
        assert eventos[0]["metadata"] == {}

    async def test_offset_cero_conserva_hora_utc(self, db, monkeypatch):
        class _Reloj:
            fijo = datetime(2026, 6, 1, 15, 0, 0)  # 15:00 UTC

            @classmethod
            def utcnow(cls):
                return cls.fijo

        monkeypatch.setattr(learning, "datetime", _Reloj)
        await learning.registrar_interaccion("5553", "message_sent", offset_min=0)
        eventos = await db.obtener_eventos_comportamiento("5553")
        assert eventos[0]["hora_dia"] == 15
        assert eventos[0]["dia_semana"] == _Reloj.fijo.weekday()

    async def test_offset_convierte_a_hora_local_cruzando_medianoche(self, db, monkeypatch):
        class _Reloj:
            fijo = datetime(2026, 6, 1, 22, 30, 0)  # 22:30 UTC

            @classmethod
            def utcnow(cls):
                return cls.fijo

        monkeypatch.setattr(learning, "datetime", _Reloj)
        # +120 min → 00:30 del día siguiente (cambia hora y día)
        await learning.registrar_interaccion("5554", "message_sent", offset_min=120)
        local_esperado = _Reloj.fijo + timedelta(minutes=120)
        eventos = await db.obtener_eventos_comportamiento("5554")
        assert eventos[0]["hora_dia"] == local_esperado.hour == 0
        assert eventos[0]["dia_semana"] == local_esperado.weekday()

    async def test_error_al_guardar_se_captura_silenciosamente(self, db, monkeypatch):
        async def boom(*a, **k):
            raise RuntimeError("DB caída")

        monkeypatch.setattr(agent.memory, "guardar_evento_comportamiento", boom)
        # No debe propagar la excepción.
        await learning.registrar_interaccion("5555", "message_sent")


# =========================================================================== #
# analizar_patrones
# =========================================================================== #
class TestAnalizarPatrones:
    async def test_menos_del_minimo_devuelve_none_sin_llamar_al_llm(self, db, monkeypatch):
        capturado = _mock_perfil_texto(monkeypatch, "no debería usarse")
        await _sembrar(db, "6001", "message_sent", n=learning.MIN_EVENTOS - 1)
        resultado = await learning.analizar_patrones("6001")
        assert resultado is None
        assert "datos" not in capturado  # cortó antes de generar el perfil

    async def test_calcula_patrones_y_persiste_perfil(self, db, monkeypatch):
        capturado = _mock_perfil_texto(monkeypatch, "PERFIL GENERADO")
        tel = "6002"

        # 14 message_sent: horas [9]*5, [10]*4, [14]*3, [20]*2  → pico 9,10,14
        horas = [9] * 5 + [10] * 4 + [14] * 3 + [20] * 2
        # días: [0]*8, [1]*4, [2]*2  → pico lunes(0), martes(1)
        dias = [0] * 8 + [1] * 4 + [2] * 2
        for h, d in zip(horas, dias):
            await _sembrar(db, tel, "message_sent", hora=h, dia=d, longitud=40)
        # 6 recordatorios → total = 20 (alcanza el mínimo)
        await _sembrar(db, tel, "reminder_created", n=6)

        resultado = await learning.analizar_patrones(tel)

        assert resultado == "PERFIL GENERADO"
        datos = capturado["datos"]
        assert datos["horas_pico"] == ["9:00", "10:00", "14:00"]
        assert datos["dias_mas_activos"] == ["lunes", "martes"]
        assert datos["prefiere_respuestas"] == "cortas"  # avg 40 < 60
        assert datos["recordatorios_creados_30d"] == 6
        assert datos["total_interacciones_30d"] == 20

        # Debe haberse persistido el perfil.
        assert await db.obtener_perfil_aprendizaje(tel) == "PERFIL GENERADO"

    async def test_brevedad_detallada_cuando_avg_es_alto(self, db, monkeypatch):
        capturado = _mock_perfil_texto(monkeypatch, "X")
        await _sembrar(db, "6003", "message_sent", longitud=100, n=learning.MIN_EVENTOS)
        await learning.analizar_patrones("6003")
        assert capturado["datos"]["prefiere_respuestas"] == "detalladas"  # avg 100 ≥ 60

    async def test_brevedad_sin_datos_cuando_no_hay_longitudes(self, db, monkeypatch):
        capturado = _mock_perfil_texto(monkeypatch, "X")
        # Eventos message_sent sin metadata de longitud.
        await _sembrar(db, "6004", "message_sent", n=learning.MIN_EVENTOS)
        await learning.analizar_patrones("6004")
        assert capturado["datos"]["prefiere_respuestas"] == "sin datos"

    async def test_dias_de_estres_filtra_estado_e_intensidad(self, db, monkeypatch):
        capturado = _mock_perfil_texto(monkeypatch, "X")
        tel = "6005"
        await _sembrar(db, tel, "message_sent", n=learning.MIN_EVENTOS)

        # Fechas relativas a ahora: la ventana de análisis es de 30 días, así que
        # deben caer dentro de ese rango. Días consecutivos → weekdays distintos.
        ahora = datetime.utcnow()
        d_estres = ahora - timedelta(days=1)   # se repite → pico
        d_agotado = ahora - timedelta(days=2)  # aparece una vez
        d_excluido = ahora - timedelta(days=3)

        async with db.async_session() as s:
            s.add_all([
                db.EventoEmocional(telefono=tel, estado="stress", intensidad=3, timestamp=d_estres),
                db.EventoEmocional(telefono=tel, estado="stress", intensidad=2, timestamp=d_estres),
                db.EventoEmocional(telefono=tel, estado="exhaustion", intensidad=2, timestamp=d_agotado),
                # Excluidos: intensidad < 2 y estado fuera del conjunto.
                db.EventoEmocional(telefono=tel, estado="stress", intensidad=1, timestamp=d_excluido),
                db.EventoEmocional(telefono=tel, estado="calm", intensidad=5, timestamp=d_excluido),
            ])
            await s.commit()

        await learning.analizar_patrones(tel)
        dias = capturado["datos"]["dias_de_estres"]
        assert dias == [learning._DIAS[d_estres.weekday()], learning._DIAS[d_agotado.weekday()]]
        assert learning._DIAS[d_excluido.weekday()] not in dias

    async def test_perfil_none_no_persiste_y_devuelve_none(self, db, monkeypatch):
        _mock_perfil_texto(monkeypatch, None)  # el generador falla / devuelve None
        tel = "6006"
        await _sembrar(db, tel, "message_sent", n=learning.MIN_EVENTOS)
        resultado = await learning.analizar_patrones(tel)
        assert resultado is None
        assert await db.obtener_perfil_aprendizaje(tel) is None


# =========================================================================== #
# _generar_perfil_texto
# =========================================================================== #
class TestGenerarPerfilTexto:
    async def test_devuelve_texto_del_llm(self, monkeypatch):
        async def fake(prompt, max_tokens=500, telefono=""):
            return "El usuario es más activo por la mañana."

        import agent.llm as llm
        monkeypatch.setattr(llm, "completar_texto", fake)
        texto = await learning._generar_perfil_texto({"horas_pico": ["9:00"]})
        assert texto == "El usuario es más activo por la mañana."

    async def test_excepcion_del_llm_devuelve_none(self, monkeypatch):
        async def boom(*a, **k):
            raise RuntimeError("LLM caído")

        import agent.llm as llm
        monkeypatch.setattr(llm, "completar_texto", boom)
        assert await learning._generar_perfil_texto({}) is None


# =========================================================================== #
# actualizar_perfiles_todos
# =========================================================================== #
class TestActualizarPerfilesTodos:
    async def test_sin_usuarios_no_hace_nada(self, monkeypatch):
        async def sin_usuarios():
            return []

        llamadas = {"analizar": 0}

        async def fake_analizar(tel):
            llamadas["analizar"] += 1
            return "x"

        monkeypatch.setattr(agent.memory, "obtener_usuarios_proactividad_activos", sin_usuarios)
        monkeypatch.setattr(learning, "analizar_patrones", fake_analizar)
        await learning.actualizar_perfiles_todos()
        assert llamadas["analizar"] == 0

    async def test_analiza_a_cada_usuario_activo(self, monkeypatch):
        async def usuarios():
            return [{"telefono": "700"}, {"telefono": "701"}, {"telefono": "702"}]

        vistos = []

        async def fake_analizar(tel):
            vistos.append(tel)
            return "perfil"

        monkeypatch.setattr(agent.memory, "obtener_usuarios_proactividad_activos", usuarios)
        monkeypatch.setattr(learning, "analizar_patrones", fake_analizar)
        await learning.actualizar_perfiles_todos()
        assert vistos == ["700", "701", "702"]

    async def test_error_de_un_usuario_no_frena_a_los_demas(self, monkeypatch):
        async def usuarios():
            return [{"telefono": "710"}, {"telefono": "711"}, {"telefono": "712"}]

        vistos = []

        async def fake_analizar(tel):
            vistos.append(tel)
            if tel == "711":
                raise RuntimeError("falla puntual")
            return "perfil"

        monkeypatch.setattr(agent.memory, "obtener_usuarios_proactividad_activos", usuarios)
        monkeypatch.setattr(learning, "analizar_patrones", fake_analizar)
        # No debe propagar; los tres usuarios se intentan.
        await learning.actualizar_perfiles_todos()
        assert vistos == ["710", "711", "712"]

    async def test_error_al_obtener_usuarios_se_captura(self, monkeypatch):
        async def boom():
            raise RuntimeError("DB caída")

        monkeypatch.setattr(agent.memory, "obtener_usuarios_proactividad_activos", boom)
        # No debe propagar la excepción.
        await learning.actualizar_perfiles_todos()
