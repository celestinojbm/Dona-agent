"""Tests de F28 · memoria de intenciones mencionadas una sola vez.

Política pura: sin red, sin BD, 0 USD. Cubre el flag, la detección (y lo que
no es intención), el filtro de datos sensibles (salud, credenciales, pago), el
vencimiento de 30 días, el copy y que el módulo no puede autorizar, enviar ni
persistir nada (no importa autonomía, automation, gate de envío ni memoria).
"""

import ast
import dataclasses
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import agent.intenciones as intenciones
from agent.intenciones import (
    DIAS_VIGENCIA,
    PREGUNTA_CHIP,
    Intencion,
    PropuestaIntencion,
    aceptar_propuesta,
    es_sensible,
    esta_vigente,
    evaluar_mensaje,
    flag_intenciones_activo,
    redactar_sugerencia,
)
from agent.intenciones import politica as pol

_ENV = "DONA_MEMORIA_INTENCIONES_ENABLED"
_AHORA = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)


def _propuesta(texto: str):
    decision = evaluar_mensaje(texto, flag=True, agente_habilitado=True)
    assert decision.razon == pol.RAZON_PROPUESTA, decision
    return decision.propuesta


# ─────────────────────────────── Flag ───────────────────────────────


class TestFlag:
    def test_apagado_por_defecto(self, monkeypatch):
        monkeypatch.delenv(_ENV, raising=False)
        assert flag_intenciones_activo() is False

    @pytest.mark.parametrize("valor", ["true", "1", "yes", "on", " TRUE ", "On"])
    def test_valores_verdaderos(self, monkeypatch, valor):
        monkeypatch.setenv(_ENV, valor)
        assert flag_intenciones_activo() is True

    @pytest.mark.parametrize("valor", ["", "false", "0", "no", "off", "si", "enabled"])
    def test_valores_falsos(self, monkeypatch, valor):
        monkeypatch.setenv(_ENV, valor)
        assert flag_intenciones_activo() is False

    def test_flag_apagado_nunca_propone(self, monkeypatch):
        monkeypatch.delenv(_ENV, raising=False)
        decision = evaluar_mensaje("Tengo que renovar el dominio en noviembre")
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_FLAG_APAGADO

    def test_flag_por_entorno(self, monkeypatch):
        monkeypatch.setenv(_ENV, "true")
        assert (
            evaluar_mensaje("Tengo que renovar el dominio", agente_habilitado=True).razon
            == pol.RAZON_PROPUESTA
        )

    def test_flag_explicito_ignora_entorno(self, monkeypatch):
        monkeypatch.setenv(_ENV, "true")
        assert evaluar_mensaje("Tengo que renovar el dominio", flag=False).propuesta is None
        monkeypatch.delenv(_ENV, raising=False)
        assert (
            evaluar_mensaje(
                "Tengo que renovar el dominio", flag=True, agente_habilitado=True
            ).propuesta
            is not None
        )

    def test_agente_apagado_por_defecto(self, monkeypatch):
        # Revisión de #332: olvidar `agente_habilitado` al cablear no enciende nada.
        monkeypatch.setenv(_ENV, "true")
        for kwargs in ({}, {"flag": True}):
            decision = evaluar_mensaje("Tengo que renovar el dominio en noviembre", **kwargs)
            assert decision.propuesta is None
            assert decision.razon == pol.RAZON_AGENTE_APAGADO

    def test_default_de_agente_es_false_en_la_firma(self):
        import inspect

        parametro = inspect.signature(evaluar_mensaje).parameters["agente_habilitado"]
        assert parametro.default is False
        assert parametro.kind is inspect.Parameter.KEYWORD_ONLY

    @pytest.mark.parametrize("valor", [1, "true", "false", "si", object(), None])
    def test_agente_solo_se_enciende_con_true_literal(self, valor):
        decision = evaluar_mensaje(
            "Tengo que renovar el dominio", flag=True, agente_habilitado=valor
        )
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_AGENTE_APAGADO

    def test_apagado_por_agente(self):
        decision = evaluar_mensaje(
            "Tengo que renovar el dominio", flag=True, agente_habilitado=False
        )
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_AGENTE_APAGADO


# ───────────────────────────── Detección ─────────────────────────────


class TestDeteccion:
    def test_ejemplo_del_roadmap(self):
        propuesta = _propuesta("Tengo que renovar el dominio en noviembre.")
        assert propuesta.texto == "renovar el dominio en noviembre"
        assert propuesta.frase_origen == "Tengo que renovar el dominio en noviembre"
        assert propuesta.pregunta == PREGUNTA_CHIP == "¿Lo recuerdo?"

    @pytest.mark.parametrize(
        ("mensaje", "esperado"),
        [
            ("tenemos que subir los precios en enero", "subir los precios en enero"),
            ("Tengo pendiente cotizar el letrero", "cotizar el letrero"),
            ("Debo mandar la factura a Pedro", "mandar la factura a Pedro"),
            ("Debemos revisar el inventario", "revisar el inventario"),
            ("Hay que cambiar el menú en diciembre", "cambiar el menú en diciembre"),
            ("Me toca renovar el seguro del local", "renovar el seguro del local"),
            ("Nos toca hacer el cierre del mes", "hacer el cierre del mes"),
            ("No se me puede olvidar comprar tóner", "comprar tóner"),
            ("no se me olvide llamar al proveedor", "llamar al proveedor"),
            ("No se me debe olvidar de pagar la renta", "pagar la renta"),
        ],
    )
    def test_disparadores(self, mensaje, esperado):
        assert _propuesta(mensaje).texto == esperado

    def test_sin_acentos_ni_mayusculas(self):
        assert _propuesta("HAY QUE PEDIR MÁS CAFÉ").texto == "PEDIR MÁS CAFÉ"

    def test_conserva_acentos_del_original(self):
        assert _propuesta("Tengo que diseñar la campaña de Año Nuevo").texto == (
            "diseñar la campaña de Año Nuevo"
        )

    def test_toma_la_frase_correcta_del_mensaje(self):
        propuesta = _propuesta(
            "Hola Dona. Ayer vendimos poco; hay que mandar la cotización a Ana el lunes!"
        )
        assert propuesta.texto == "mandar la cotización a Ana el lunes"
        assert propuesta.frase_origen == "hay que mandar la cotización a Ana el lunes"

    def test_punto_de_dominio_no_parte_la_frase(self):
        # Regresión: el «.» de un dominio no es fin de frase.
        propuesta = _propuesta("Tengo que renovar usadona.com antes del 30. Gracias")
        assert propuesta.texto == "renovar usadona.com antes del 30"

    def test_primera_intencion_del_mensaje(self):
        propuesta = _propuesta("Tengo que renovar el dominio. Debo pagar la luz")
        assert propuesta.texto == "renovar el dominio"

    def test_frase_en_una_sola_linea(self):
        # El salto de línea corta la frase; los espacios múltiples se colapsan.
        propuesta = _propuesta("tengo que   llamar   a\tMarta\notra cosa")
        assert propuesta.texto == "llamar a Marta"

    @pytest.mark.parametrize(
        "mensaje",
        [
            "",
            "   ",
            "Hola Dona, ¿cómo vamos?",
            "Necesito un logo para mi cafetería",  # pedido para ahora, no intención
            "¿Tengo que pagar el IVA este mes?",  # pregunta a Dona
            "No tengo que hacer nada hoy",
            "Ya no debo nada al proveedor",
            "Nunca hay que rendirse",
            "Recuérdame mañana a las 9 que tengo que llamar a Ana",  # lo resuelve reminders_nl
            "tengo que ir",  # sin contenido útil
            "Hay que",
        ],
    )
    def test_no_es_intencion(self, mensaje):
        decision = evaluar_mensaje(mensaje, flag=True, agente_habilitado=True)
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_SIN_INTENCION

    @pytest.mark.parametrize("valor", [None, 123, ["tengo que renovar el dominio"]])
    def test_entrada_no_string(self, valor):
        decision = evaluar_mensaje(valor, flag=True, agente_habilitado=True)
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_SIN_INTENCION

    def test_negacion_no_bloquea_otra_ocurrencia(self):
        propuesta = _propuesta("No tengo que ir hoy, pero tengo que llamar a Marta mañana")
        assert propuesta.texto == "llamar a Marta mañana"

    def test_recorta_textos_largos(self):
        largo = "Tengo que " + "revisar cada pedido pendiente " * 20
        propuesta = _propuesta(largo)
        assert len(propuesta.texto) <= pol.LARGO_MAXIMO_TEXTO
        assert len(propuesta.frase_origen) <= pol.LARGO_MAXIMO_FRASE
        assert propuesta.texto.endswith("…")
        assert propuesta.frase_origen.endswith("…")


# ─────────────────────────── Datos sensibles ───────────────────────────


class TestSensibles:
    @pytest.mark.parametrize(
        "mensaje",
        [
            # Salud
            "Tengo que ir al médico el martes",
            "tengo que sacar cita con el doctor",
            "Debo tomar la pastilla a las 8",
            "Tengo que recoger los resultados del análisis de sangre",
            "Me toca terapia el jueves",
            "Tengo que llevar la receta médica a la farmacia",
            # Credenciales
            "Debo cambiar la contraseña del banco",
            "Tengo que mandarle la clave del wifi a Luis",
            "Hay que rotar el API key de Stripe",
            "Tengo que pasarle el código de verificación",
            "tengo que entrar a usadona.com/login?t=abc123",
            "Tengo que actualizar mi PIN",
            # Pago
            "tengo que pagar con 4111 1111 1111 1111",
            "Tengo que pagar con 4111-1111-1111-1111",
            "Debo mandarle el número de cuenta a Carlos",
            "Tengo que dar el CVV de la tarjeta",
            "Hay que registrar mi seguro social",
        ],
    )
    def test_rechaza(self, mensaje):
        decision = evaluar_mensaje(mensaje, flag=True, agente_habilitado=True)
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_DATO_SENSIBLE

    def test_sensible_corta_todo_el_mensaje(self):
        # Fail-closed: no busca otra frase si la primera intención es sensible.
        decision = evaluar_mensaje(
            "Tengo que ir al médico. Tengo que renovar el dominio",
            flag=True,
            agente_habilitado=True,
        )
        assert decision.razon == pol.RAZON_DATO_SENSIBLE

    def test_sensible_fuera_de_la_intencion_no_bloquea(self):
        propuesta = _propuesta("Ayer fui al médico. Tengo que renovar el dominio")
        assert propuesta.texto == "renovar el dominio"

    @pytest.mark.parametrize(
        "mensaje",
        [
            "Tengo que pagar la renta del local",  # un pago no es un dato de pago
            "Tengo que llamar al 305 555 0199",  # teléfono de 10 dígitos
            "Tengo que revisar el pedido 48219",
        ],
    )
    def test_no_sobrebloquea(self, mensaje):
        assert (
            evaluar_mensaje(mensaje, flag=True, agente_habilitado=True).razon == pol.RAZON_PROPUESTA
        )

    @pytest.mark.parametrize("valor", [None, 42, b"contrasena", ["texto"]])
    def test_es_sensible_no_string_falla_cerrado(self, valor):
        # Algo que no es texto no se pudo revisar: cuenta como sensible.
        assert es_sensible(valor) is True

    def test_es_sensible_sin_acentos(self):
        assert es_sensible("CONTRASEÑA") is True
        assert es_sensible("medico") is True
        assert es_sensible("diagnóstico") is True


class _PatronRoto:
    """Simula un fallo del filtro (regex corrupto, bug futuro, etc.)."""

    def search(self, _texto):
        raise RuntimeError("filtro roto")


class TestFallaCerrado:
    """Revisión de #332: ante error del filtro, no se propone ni se guarda."""

    def test_es_sensible_ante_excepcion_devuelve_true(self, monkeypatch):
        monkeypatch.setattr(pol, "_SENSIBLES", (_PatronRoto(),))
        assert es_sensible("Tengo que renovar el dominio") is True

    def test_es_sensible_ante_error_de_normalizacion(self, monkeypatch):
        def _roto(_texto):
            raise UnicodeError("normalización rota")

        monkeypatch.setattr(pol, "_normalizar", _roto)
        assert es_sensible("Tengo que renovar el dominio") is True

    def test_error_no_registra_el_texto(self, monkeypatch, caplog):
        monkeypatch.setattr(pol, "_SENSIBLES", (_PatronRoto(),))
        with caplog.at_level("WARNING", logger=pol.__name__):
            es_sensible("Tengo que cambiar la contraseña Hunter2")
        assert "RuntimeError" in caplog.text
        assert "Hunter2" not in caplog.text

    def test_evaluar_con_filtro_roto_no_propone(self, monkeypatch):
        monkeypatch.setattr(pol, "_SENSIBLES", (_PatronRoto(),))
        decision = evaluar_mensaje(
            "Tengo que renovar el dominio en noviembre", flag=True, agente_habilitado=True
        )
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_DATO_SENSIBLE

    def test_evaluar_ante_error_inesperado_no_propone(self, monkeypatch):
        def _roto(_texto):
            raise RuntimeError("detección rota")

        monkeypatch.setattr(pol, "_frases", _roto)
        decision = evaluar_mensaje(
            "Tengo que renovar el dominio en noviembre", flag=True, agente_habilitado=True
        )
        assert decision.propuesta is None
        assert decision.razon == pol.RAZON_ERROR

    def test_aceptar_con_filtro_roto_no_guarda(self, monkeypatch):
        propuesta = _propuesta("Tengo que renovar el dominio")
        monkeypatch.setattr(pol, "_SENSIBLES", (_PatronRoto(),))
        with pytest.raises(ValueError, match="sensibles"):
            aceptar_propuesta(propuesta, ahora=_AHORA)

    def test_aceptar_con_campo_no_string_no_guarda(self):
        # Una propuesta construida a mano con basura no debe pasar el filtro.
        propuesta = PropuestaIntencion(texto=None, frase_origen="Tengo que renovar el dominio")
        with pytest.raises(ValueError, match="sensibles"):
            aceptar_propuesta(propuesta, ahora=_AHORA)


# ───────────────────────── Aceptar y vencimiento ─────────────────────────


class TestAceptar:
    def test_vence_a_los_30_dias(self):
        intencion = aceptar_propuesta(_propuesta("Tengo que renovar el dominio"), ahora=_AHORA)
        assert DIAS_VIGENCIA == 30
        assert intencion.creada_en == _AHORA
        assert intencion.vence_en == _AHORA + timedelta(days=30)
        assert intencion.texto == "renovar el dominio"
        assert intencion.frase_origen == "Tengo que renovar el dominio"

    def test_vigencia(self):
        intencion = aceptar_propuesta(_propuesta("Tengo que renovar el dominio"), ahora=_AHORA)
        assert esta_vigente(intencion, ahora=_AHORA)
        assert esta_vigente(intencion, ahora=_AHORA + timedelta(days=29, hours=23))
        assert not esta_vigente(intencion, ahora=_AHORA + timedelta(days=30))
        assert not esta_vigente(intencion, ahora=_AHORA + timedelta(days=45))

    def test_vigencia_en_otra_zona_horaria(self):
        intencion = aceptar_propuesta(_propuesta("Tengo que renovar el dominio"), ahora=_AHORA)
        este = timezone(timedelta(hours=-5))
        justo_antes = (_AHORA + timedelta(days=30) - timedelta(seconds=1)).astimezone(este)
        assert esta_vigente(intencion, ahora=justo_antes)

    def test_exige_zona_horaria(self):
        propuesta = _propuesta("Tengo que renovar el dominio")
        with pytest.raises(ValueError):
            aceptar_propuesta(propuesta, ahora=datetime(2026, 11, 21, 15, 0))
        intencion = aceptar_propuesta(propuesta, ahora=_AHORA)
        with pytest.raises(ValueError):
            esta_vigente(intencion, ahora=datetime(2026, 11, 21, 15, 0))
        with pytest.raises(ValueError):
            aceptar_propuesta(propuesta, ahora="2026-11-21")

    def test_revalida_sensibles_en_propuesta_hecha_a_mano(self):
        with pytest.raises(ValueError):
            aceptar_propuesta(PropuestaIntencion("cambiar la contraseña", "x"), ahora=_AHORA)
        with pytest.raises(ValueError):
            aceptar_propuesta(
                PropuestaIntencion("ir a la cita", "Tengo que ir al médico"), ahora=_AHORA
            )

    def test_rechaza_vacia_o_tipo_incorrecto(self):
        with pytest.raises(ValueError):
            aceptar_propuesta(PropuestaIntencion("  ", "Tengo que"), ahora=_AHORA)
        with pytest.raises(TypeError):
            aceptar_propuesta({"texto": "renovar el dominio"}, ahora=_AHORA)

    def test_objetos_inmutables(self):
        intencion = aceptar_propuesta(_propuesta("Tengo que renovar el dominio"), ahora=_AHORA)
        with pytest.raises(dataclasses.FrozenInstanceError):
            intencion.vence_en = _AHORA + timedelta(days=365)


# ───────────────────── Nunca autoriza ni ejecuta ─────────────────────


class TestNuncaAutoriza:
    def test_intencion_sin_campos_de_permiso(self):
        campos = {f.name for f in dataclasses.fields(Intencion)}
        assert campos == {"texto", "frase_origen", "creada_en", "vence_en"}
        prohibidos = ("autoriz", "nivel", "aprob", "permiso", "credito", "monto")
        for clase in (Intencion, PropuestaIntencion):
            for campo in dataclasses.fields(clase):
                assert not any(p in campo.name for p in prohibidos), campo.name

    def test_sugerencia_pide_confirmacion(self):
        intencion = aceptar_propuesta(
            _propuesta("Tengo que renovar el dominio en noviembre"), ahora=_AHORA
        )
        texto = redactar_sugerencia(intencion)
        assert texto == (
            "Me dijiste: «Tengo que renovar el dominio en noviembre». "
            "¿Preparo algo para eso? No hago nada sin tu confirmación."
        )
        assert "confirmación" in texto


# ─────────────────────────── Aislamiento ───────────────────────────

_PROHIBIDOS = (
    "agent.autonomia",
    "agent.automation",
    "agent.envio_gate",
    "agent.providers",
    "agent.main",
    "agent.billing",
    "agent.brain",
    "agent.memory",
    "agent.vector_memory",
    "agent.canales",
    "sqlalchemy",
    "httpx",
)


def _imports(ruta: Path) -> set[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    return modulos


class TestAislamiento:
    def test_ningun_archivo_del_paquete_importa_prohibidos(self):
        archivos = sorted(Path(intenciones.__file__).parent.glob("*.py"))
        assert archivos
        for ruta in archivos:
            importados = _imports(ruta)
            for prohibido in _PROHIBIDOS:
                assert not any(
                    m == prohibido or m.startswith(prohibido + ".") for m in importados
                ), f"{ruta.name} importa {prohibido}"
            fuente = ruta.read_text(encoding="utf-8")
            assert "importlib" not in fuente and "__import__" not in fuente, ruta.name

    def test_importar_el_paquete_no_carga_nada_mas(self):
        raiz = Path(intenciones.__file__).resolve().parents[2]
        codigo = (
            "import sys; import agent.intenciones; "
            "print('\\n'.join(sorted(m for m in sys.modules if m.startswith('agent'))))"
        )
        salida = subprocess.run(
            [sys.executable, "-c", codigo], cwd=raiz, capture_output=True, text=True, check=True
        ).stdout.split()
        assert set(salida) == {"agent", "agent.intenciones", "agent.intenciones.politica"}

    def test_no_cableado_en_main_ni_brain(self):
        raiz = Path(intenciones.__file__).resolve().parents[1]
        for nombre in ("main.py", "brain.py", "memory.py"):
            fuente = (raiz / nombre).read_text(encoding="utf-8")
            assert "agent.intenciones" not in fuente, nombre
