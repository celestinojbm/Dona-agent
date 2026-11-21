"""Tests de F35 — WhatsApp solo para avisos y aprobaciones (política de canal).

Política pura: sin red, 0 USD, sin proveedor real y sin envío. Cubre el flag,
la decisión de canal (fail-closed con el flag encendido, compatibilidad con el
flag apagado), el copy breve app-first, el encaje con el aviso terminal de F14
y que el módulo no depende del gate de envío ni de los proveedores.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import agent.canales as canales
from agent.canales import (
    PROPOSITOS_WHATSAPP,
    DecisionCanal,
    decidir_canal,
    flag_solo_avisos_activo,
    redactar_aprobacion,
    redactar_aviso,
)
from agent.canales import politica_whatsapp as pol
from agent.plan_vivo.formato import notificacion_terminal

_ENV = "DONA_WHATSAPP_SOLO_AVISOS_ENABLED"
_DENEGADOS_CONOCIDOS = ("conversacion", "proactividad", "onboarding", "creativo")


@pytest.fixture
def _flag_on(monkeypatch):
    monkeypatch.setenv(_ENV, "true")


@pytest.fixture
def _flag_off(monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)


# ───────────────────── Flag ─────────────────────

class TestFlag:
    def test_ausente_es_apagado(self, _flag_off):
        assert flag_solo_avisos_activo() is False

    @pytest.mark.parametrize("valor", ["", "   ", "false", "0", "no", "off", "sí", "2"])
    def test_valores_que_no_encienden(self, monkeypatch, valor):
        monkeypatch.setenv(_ENV, valor)
        assert flag_solo_avisos_activo() is False

    @pytest.mark.parametrize("valor", ["true", "1", "yes", "on", "  true  ", "TRUE", "True"])
    def test_valores_que_encienden(self, monkeypatch, valor):
        monkeypatch.setenv(_ENV, valor)
        assert flag_solo_avisos_activo() is True

    def test_se_lee_en_cada_llamada(self, monkeypatch):
        monkeypatch.setenv(_ENV, "true")
        assert flag_solo_avisos_activo() is True
        monkeypatch.setenv(_ENV, "false")
        assert flag_solo_avisos_activo() is False


# ───────────────────── Decisión con flag apagado ─────────────────────

class TestFlagApagado:
    @pytest.mark.parametrize("proposito", ["conversacion", "aviso", "newsletter", "", "   "])
    def test_todo_permitido_por_compatibilidad(self, _flag_off, proposito):
        d = decidir_canal(proposito)
        assert d.permitido_whatsapp is True
        assert d.razon == "flag_apagado"
        assert d.destino == "whatsapp"

    def test_conversacion_y_aviso_criterio_4(self, _flag_off):
        for proposito in ("conversacion", "aviso"):
            d = decidir_canal(proposito)
            assert (d.permitido_whatsapp, d.razon) == (True, "flag_apagado")


# ───────────────────── Decisión con flag encendido ─────────────────────

class TestFlagEncendido:
    def test_propositos_permitidos(self):
        assert PROPOSITOS_WHATSAPP == frozenset({"aviso", "aprobacion", "cumplimiento_tcpa"})

    @pytest.mark.parametrize("proposito", sorted(PROPOSITOS_WHATSAPP))
    def test_permitidos_salen_por_whatsapp(self, _flag_on, proposito):
        d = decidir_canal(proposito)
        assert d == DecisionCanal(True, proposito, "proposito_permitido", "whatsapp")

    @pytest.mark.parametrize("proposito", _DENEGADOS_CONOCIDOS)
    def test_conocidos_no_permitidos_van_a_la_app(self, _flag_on, proposito):
        d = decidir_canal(proposito)
        assert d.permitido_whatsapp is False
        assert d.destino == "app"
        assert d.razon == "proposito_no_permitido"

    @pytest.mark.parametrize("proposito", ["newsletter", "avsio", "aprobación", "desconocido", "", "   "])
    def test_desconocido_typo_y_vacio_fail_closed(self, _flag_on, proposito):
        d = decidir_canal(proposito)
        assert d.permitido_whatsapp is False
        assert d.destino == "app"
        assert d.razon == "proposito_desconocido"

    @pytest.mark.parametrize("proposito", [None, 123, ["aviso"], b"aviso"])
    def test_no_string_fail_closed(self, _flag_on, proposito):
        d = decidir_canal(proposito)
        assert d.permitido_whatsapp is False
        assert d.destino == "app"
        assert d.proposito == ""

    @pytest.mark.parametrize("crudo", ["Aviso", "  AVISO  ", "\taprobacion\n", "Cumplimiento_TCPA"])
    def test_normaliza_mayusculas_y_espacios(self, _flag_on, crudo):
        d = decidir_canal(crudo)
        assert d.permitido_whatsapp is True
        assert d.proposito == crudo.strip().lower()

    def test_decision_es_inmutable(self, _flag_on):
        d = decidir_canal("aviso")
        with pytest.raises(AttributeError):
            d.permitido_whatsapp = False  # type: ignore[misc]


# ───────────────────── Inyección explícita del flag ─────────────────────

class TestFlagInyectado:
    def test_flag_true_ignora_env_apagado(self, _flag_off):
        d = decidir_canal("conversacion", flag=True)
        assert (d.permitido_whatsapp, d.destino) == (False, "app")

    def test_flag_false_ignora_env_encendido(self, _flag_on):
        d = decidir_canal("conversacion", flag=False)
        assert (d.permitido_whatsapp, d.razon) == (True, "flag_apagado")


# ───────────────────── Copy breve ─────────────────────

class TestCopy:
    def test_aviso_menciona_la_app(self):
        texto = redactar_aviso("Tu reporte semanal está listo")
        assert texto == "Tu reporte semanal está listo. Revisa el detalle en la app."

    def test_aviso_sin_detalle_no_menciona_la_app(self):
        assert redactar_aviso("Listo", detalle_en_app=False) == "Listo."

    def test_aviso_no_duplica_signos(self):
        assert redactar_aviso("¿Todo bien?", detalle_en_app=False) == "¿Todo bien?"
        assert redactar_aviso("Listo.", detalle_en_app=False) == "Listo."

    def test_aprobacion_pide_autorizar_en_la_app(self):
        texto = redactar_aprobacion("Enviar cotización a Acme")
        assert "aprobación" in texto
        assert "autorízalo en la app" in texto
        assert "Enviar cotización a Acme" in texto

    def test_quita_markdown_y_saltos_de_linea(self):
        texto = redactar_aviso("*Plan* `cambiado`\n\n- paso 1\n~x~")
        assert "*" not in texto and "`" not in texto and "~" not in texto
        assert "\n" not in texto

    @pytest.mark.parametrize("titulo", ["", "   ", None])
    def test_titulo_vacio_tiene_texto_por_defecto(self, titulo):
        assert redactar_aviso(titulo).startswith("Tienes un aviso nuevo.")
        assert "una acción pendiente" in redactar_aprobacion(titulo)

    @pytest.mark.parametrize("detalle", [True, False])
    def test_titulo_enorme_se_recorta_aviso(self, detalle):
        texto = redactar_aviso("a" * 1000, detalle_en_app=detalle)
        assert len(texto) <= 200
        assert "…" in texto
        if detalle:
            assert texto.endswith("Revisa el detalle en la app.")

    def test_titulo_enorme_se_recorta_aprobacion(self):
        texto = redactar_aprobacion("b" * 1000)
        assert len(texto) <= 200
        assert "…" in texto
        assert texto.endswith("en la app.")

    @pytest.mark.parametrize("titulo", ["Listo", "Firma pendiente del contrato", "x" * 300])
    def test_sin_urls_ni_tokens(self, titulo):
        for texto in (redactar_aviso(titulo), redactar_aprobacion(titulo)):
            assert len(texto) <= 200
            assert "http://" not in texto and "https://" not in texto
            assert "token" not in texto.lower()

    @pytest.mark.parametrize(
        "titulo",
        [
            "Firma aquí https://usadona.com/firmar?token=abc123",
            "Firma en http://ejemplo.com/x",
            "Abre www.ejemplo.com/aprobar ya",
            "Autoriza en usadona.com/a?t=deadbeef",
            "Escríbeme a wa.me/13055550199",
            "HTTPS://EJEMPLO.COM/X",
        ],
    )
    def test_titulo_con_url_no_la_arrastra(self, titulo):
        # Regresión: el título viene del llamador y antes pasaba tal cual
        # (magic links y tokens en query string acababan en WhatsApp).
        for texto in (redactar_aviso(titulo), redactar_aprobacion(titulo)):
            bajo = texto.lower()
            assert "http" not in bajo and "www." not in bajo and "/" not in bajo
            assert "token" not in bajo and "deadbeef" not in bajo and "abc123" not in bajo

    @pytest.mark.parametrize(
        "titulo",
        ["Llama al +1 (305) 555-0199", "Llama al (305) 555-0199", "Llama al 305.555.0199",
         "Llama al 3055550199", "Llama al +5215512345678"],
    )
    def test_titulo_con_telefono_no_lo_arrastra(self, titulo):
        for texto in (redactar_aviso(titulo), redactar_aprobacion(titulo)):
            assert "555" not in texto and "5512345678" not in texto

    @pytest.mark.parametrize(
        "titulo",
        [
            # Seguimiento de #329: enlaces sin `/` y esquemas sin `//`.
            "Autoriza en usadona.com?t=SECRETO123",
            "Autoriza en usadona.com#t=SECRETO123",
            "Autoriza en usadona.com:8443?t=SECRETO123",
            "Firma: ?t=SECRETO123",
            "Firma: &token=SECRETO123",
            "Escribe a mailto:soporte@usadona.com?subject=SECRETO123",
            "Pulsa javascript:alert(SECRETO123)",
            "Llama tel:+13055550199",
            "Llama tel:3055550199;SECRETO123",
            "Abre data:text/html,SECRETO123",
        ],
    )
    def test_titulo_con_enlace_sin_barra_no_lo_arrastra(self, titulo):
        for texto in (redactar_aviso(titulo), redactar_aprobacion(titulo)):
            bajo = texto.lower()
            assert "secreto123" not in bajo
            assert "usadona.com" not in bajo and "token" not in bajo
            for esquema in ("mailto:", "javascript:", "tel:", "data:"):
                assert esquema not in bajo
            assert "555" not in bajo and "@" not in bajo

    @pytest.mark.parametrize(
        "titulo",
        [
            "Nuevo pedido de juan.perez@cliente.com",
            "Nuevo pedido de Juan.Perez+vip@Cliente.co.uk.",
            "Contacto: ana_l@sub.dominio.mx, pendiente",
            "Pedido de juan.perez@cliente.com/x",
        ],
    )
    def test_correos_del_cliente_no_salen(self, titulo):
        for texto in (redactar_aviso(titulo), redactar_aprobacion(titulo)):
            bajo = texto.lower()
            assert "@" not in bajo
            assert "juan" not in bajo and "perez" not in bajo and "ana_l" not in bajo
            assert "cliente" not in bajo and "dominio" not in bajo

    @pytest.mark.parametrize(
        "titulo",
        ["Pedido 4821903377 enviado", "Pedido #4821903377 enviado", "Orden 48219033771 lista",
         "Referencia 1234567890"],
    )
    def test_numero_de_pedido_se_conserva(self, titulo):
        # Antes cualquier número de 10 dígitos se borraba como teléfono y el
        # aviso perdía la referencia del pedido.
        assert redactar_aviso(titulo, detalle_en_app=False) == f"{titulo}."

    @pytest.mark.parametrize(
        "titulo",
        ["Llama al 3055550199", "Tel. 3055550199", "Tel: 3055550199", "WhatsApp: 13055550199",
         "Llámame al 305-555-0199", "Cliente 305 555 0199 espera", "Móvil 3055550199"],
    )
    def test_telefono_con_forma_o_pista_se_sigue_quitando(self, titulo):
        for texto in (redactar_aviso(titulo), redactar_aprobacion(titulo)):
            assert "555" not in texto and "0199" not in texto

    @pytest.mark.parametrize(
        "titulo",
        ["Reunión 2026-11-20 10:30", "Factura #4821 por 1,250 USD", "-5 % de descuento",
         "Versión 2.5 publicada"],
    )
    def test_fechas_e_importes_se_conservan(self, titulo):
        assert redactar_aviso(titulo, detalle_en_app=False) == f"{titulo}."

    def test_quita_cursiva_pero_conserva_snake_case(self):
        texto = redactar_aviso("_urgente_ revisar cumplimiento_tcpa", detalle_en_app=False)
        assert texto == "urgente revisar cumplimiento_tcpa."

    @pytest.mark.parametrize("titulo", ["> Plan cambiado", "- Plan cambiado", "• Plan cambiado"])
    def test_quita_cita_y_vineta_inicial(self, titulo):
        assert redactar_aviso(titulo, detalle_en_app=False) == "Plan cambiado."

    @pytest.mark.parametrize("titulo", ["Pago:", "Hola,", "Listo;", "Listo ...", "Listo. "])
    def test_no_deja_puntuacion_colgante(self, titulo):
        texto = redactar_aviso(titulo, detalle_en_app=False)
        assert texto in ("Pago.", "Hola.", "Listo.")

    def test_solo_url_usa_texto_por_defecto(self):
        assert redactar_aviso("https://usadona.com/x").startswith("Tienes un aviso nuevo.")
        assert "una acción pendiente" in redactar_aprobacion("https://usadona.com/x")

    def test_copy_no_consulta_el_flag(self, monkeypatch):
        monkeypatch.setenv(_ENV, "true")
        con_flag = (redactar_aviso("Hola"), redactar_aprobacion("Hola"))
        monkeypatch.delenv(_ENV)
        assert con_flag == (redactar_aviso("Hola"), redactar_aprobacion("Hola"))


# ───────────────────── Encaje con F14 ─────────────────────

class TestEncajeF14:
    @pytest.mark.parametrize("estado", ["completado", "parcial", "fallido", "cancelado"])
    def test_aviso_terminal_es_aviso_permitido(self, _flag_on, estado):
        texto = notificacion_terminal({"estado": estado})
        assert texto, "F14 debe devolver un aviso terminal"
        assert decidir_canal("aviso").permitido_whatsapp is True

    @pytest.mark.parametrize("estado", ["en_curso", "preparado"])
    def test_estados_en_curso_no_generan_aviso(self, estado):
        assert notificacion_terminal({"estado": estado}) is None

    def test_mismo_tono_que_f14(self):
        cierre_f14 = notificacion_terminal({"estado": "fallido"})
        assert cierre_f14.endswith("Revisa el detalle en la app.")
        assert redactar_aviso("No pude completar la tarea").endswith("Revisa el detalle en la app.")

    @pytest.mark.parametrize("estado", ["completado", "parcial", "fallido", "cancelado"])
    def test_envolver_aviso_f14_no_duplica_la_coletilla(self, estado):
        # Regresión: redactar_aviso(notificacion_terminal(...)) repetía
        # «Revisa el detalle en la app.» dos veces en parcial/fallido.
        texto = redactar_aviso(notificacion_terminal({"estado": estado}))
        assert texto.count("Revisa el detalle en la app") == 1
        assert texto.endswith("Revisa el detalle en la app.")

    @pytest.mark.parametrize("coletilla", ["Revisa el detalle en la app.", "revisa el detalle en la app"])
    def test_titulo_largo_con_coletilla_la_conserva_una_vez(self, coletilla):
        texto = redactar_aviso("x" * 300 + " " + coletilla)
        assert len(texto) <= 200
        assert texto.count("Revisa el detalle en la app") == 1
        assert texto.endswith("… Revisa el detalle en la app.")

    def test_solo_la_coletilla_usa_texto_por_defecto(self):
        texto = redactar_aviso("Revisa el detalle en la app.")
        assert texto == "Tienes un aviso nuevo. Revisa el detalle en la app."


# ───────────────────── Aislamiento del gate de envío ─────────────────────

_PROHIBIDOS = ("agent.envio_gate", "agent.providers", "agent.main", "agent.billing")


def _imports(ruta: Path) -> set[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
            modulos.update(f"{nodo.module}.{alias.name}" for alias in nodo.names)
    return modulos


class TestAislamiento:
    @pytest.mark.parametrize("modulo", [pol, canales])
    def test_modulo_no_importa_gate_ni_proveedores(self, modulo):
        importados = _imports(Path(modulo.__file__))
        for prohibido in _PROHIBIDOS:
            assert not any(m == prohibido or m.startswith(prohibido + ".") for m in importados), (
                f"{modulo.__name__} importa {prohibido}"
            )

    def test_fuente_no_menciona_puede_enviar(self):
        fuente = Path(pol.__file__).read_text(encoding="utf-8")
        assert "puede_enviar(" not in fuente
        assert "import agent.providers" not in fuente
        assert "from agent.providers" not in fuente
        assert "from agent.envio_gate" not in fuente

    def test_este_test_no_importa_prohibidos(self):
        importados = _imports(Path(__file__))
        for prohibido in _PROHIBIDOS:
            assert not any(m == prohibido or m.startswith(prohibido + ".") for m in importados)

    def test_espacio_de_nombres_sin_referencias(self):
        for valor in vars(pol).values():
            nombre = getattr(valor, "__name__", "")
            assert not any(nombre.startswith(p) for p in _PROHIBIDOS)

    def test_ningun_archivo_del_paquete_importa_prohibidos(self):
        # Cubre también archivos que se añadan después a agent/canales/, no
        # solo los dos de hoy.
        archivos = sorted(Path(canales.__file__).parent.glob("*.py"))
        assert archivos
        for ruta in archivos:
            importados = _imports(ruta)
            for prohibido in _PROHIBIDOS:
                assert not any(m == prohibido or m.startswith(prohibido + ".") for m in importados), (
                    f"{ruta.name} importa {prohibido}"
                )
            fuente = ruta.read_text(encoding="utf-8")
            # Importación dinámica: el análisis AST de arriba no la ve.
            assert "importlib" not in fuente and "__import__" not in fuente, ruta.name

    def test_importar_el_paquete_no_carga_nada_mas(self):
        # Chequeo transitivo en un proceso limpio: otros tests ya cargaron
        # envio_gate/providers en este, así que sys.modules aquí no sirve.
        raiz = Path(canales.__file__).resolve().parents[2]
        codigo = (
            "import sys; import agent.canales; "
            "print('\\n'.join(sorted(m for m in sys.modules if m.startswith('agent'))))"
        )
        salida = subprocess.run(
            [sys.executable, "-c", codigo], cwd=raiz, capture_output=True, text=True, check=True
        ).stdout.split()
        assert set(salida) == {"agent", "agent.canales", "agent.canales.politica_whatsapp"}
