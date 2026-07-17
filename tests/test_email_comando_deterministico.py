# tests/test_email_comando_deterministico.py — PR 1 · Parsing exacto ENVIAR/CANCELAR

import pytest

from agent.automation.email_actions import parsear_comando_confirmacion


class TestComandosAceptados:
    @pytest.mark.parametrize("texto,esperado", [
        ("ENVIAR AB2K79XM4T", ("enviar", "AB2K79XM4T")),
        ("enviar ab2k79xm4t", ("enviar", "AB2K79XM4T")),
        ("ENVIAR AB2K7 9XM4T", ("enviar", "AB2K79XM4T")),
        ("ENVIAR AB2K7-9XM4T", ("enviar", "AB2K79XM4T")),
        ("  ENVIAR AB2K79XM4T  ", ("enviar", "AB2K79XM4T")),
        ("Dona ENVIAR AB2K79XM4T", ("enviar", "AB2K79XM4T")),
        ("dona enviar AB2K7 9XM4T", ("enviar", "AB2K79XM4T")),
        ("CANCELAR AB2K79XM4T", ("cancelar", "AB2K79XM4T")),
        ("dona cancelar ab2k7 9xm4t", ("cancelar", "AB2K79XM4T")),
        # Normalización Crockford dentro del comando (O→0)
        ("ENVIAR OB2K79XM4T", ("enviar", "0B2K79XM4T")),
    ])
    def test_matchea_y_normaliza(self, texto, esperado):
        assert parsear_comando_confirmacion(texto) == esperado


class TestComandosRechazados:
    @pytest.mark.parametrize("texto", [
        # Los cuatro casos explícitos de la spec
        "no envíes AB2K79XM4T",
        "sí, envíalo",
        "ENVIAR mañana AB2K79XM4T",
        "creo que ENVIAR AB2K79XM4T",
        # Otras variantes que NO deben confirmar
        "",
        "ENVIAR",
        "CANCELAR",
        "ENVIAR ABC",                       # token corto
        "ENVIAR AB2K79XM4T ya",             # palabra extra → longitud inválida
        "ENVIAR AB2K79XM4T CANCELAR",       # dos cosas
        "ENVIARAB2K79XM4T",                 # sin espacio
        "por favor ENVIAR AB2K79XM4T",      # prefijo no permitido
        "dona dona ENVIAR AB2K79XM4T",      # doble prefijo
        "ENVIAR AB2K79XM4U",                # U fuera del alfabeto Crockford
        "reenviar AB2K79XM4T",              # substring del verbo
        "ENVIAR el correo",
        "enviar 12345678901",               # 11 chars
    ])
    def test_no_matchea(self, texto):
        assert parsear_comando_confirmacion(texto) is None


class TestRutaEnMain:
    def test_main_parsea_antes_del_llm(self):
        """El parseo determinístico vive en procesar_webhook ANTES de
        generar_respuesta (CLAUDE.md §3.2): el LLM no es el gate."""
        import inspect

        import agent.main as main_mod

        src = inspect.getsource(main_mod.procesar_webhook)
        pos_parse = src.find("parsear_comando_confirmacion")
        pos_llm = src.find("generar_respuesta(")
        assert pos_parse != -1, "main.py debe parsear ENVIAR/CANCELAR"
        assert pos_llm != -1
        assert pos_parse < pos_llm, "el parseo debe ocurrir antes del LLM"

    def test_main_enhebra_mensaje_id(self):
        import inspect

        import agent.main as main_mod

        src = inspect.getsource(main_mod.procesar_webhook)
        assert "mensaje_id=msg.mensaje_id" in src
