# tests/test_creativos_comandos_render.py — Cobertura de parsers y renderers puros
# de agent/creativos/comandos.py que no tenían test dedicado.
#
# CLAUDE.md §3.2: los comandos determinísticos (imagen, video, voz, documento,
# quitar fondo) se detectan con regex ANTES del LLM. Este módulo es 100% puro
# (regex + formateo de texto, sin DB, sin I/O, sin red), así que fijamos su
# COMPORTAMIENTO ACTUAL contra regresiones sin tocar producción.
#
# Cubre lo que test_creativos_imagen.py / test_creativos_ajustar.py no tocaban:
#   - parsers: video, video con avatar, documento, voz, quitar fondo
#   - detección "sin sujeto" e "inequívocos" de confirmar/cancelar
#   - TODOS los renderers texto_* (preview / encolada / avisos) y helpers
#     (_fmt_moneda, _linea_reemplazo)
#
# Las aserciones son sobre subcadenas estables (íconos, etiquetas, montos),
# no strings completos, para no volverse frágiles ante retoques de copy.

import pytest

from agent.creativos import comandos as c


# ─────────────────────────────────────────────────────────────────────────────
# Parser: quitar fondo (Photoroom)
# ─────────────────────────────────────────────────────────────────────────────
class TestBgRemove:
    @pytest.mark.parametrize(
        "caption",
        [
            "quita el fondo",
            "quítame el fondo",
            "sin fondo",
            "fondo transparente",
            "remove background",
            "elimina el fondo",
            "bg remove",
        ],
    )
    def test_caption_pide_quitar_fondo(self, caption):
        assert c.es_comando_bg_remove(caption) is True

    @pytest.mark.parametrize("caption", ["hola qué tal", "una foto de mi perro", ""])
    def test_caption_benigno_no_dispara(self, caption):
        assert c.es_comando_bg_remove(caption) is False

    def test_caption_none_no_falla(self):
        assert c.es_comando_bg_remove(None) is False

    @pytest.mark.parametrize(
        "texto",
        [
            "quita el fondo a la imagen",
            "quita el fondo de la foto",
            "remove background a la última imagen",
        ],
    )
    def test_ultima_requiere_frase_y_referencia(self, texto):
        assert c.es_comando_bg_remove_ultima(texto) is True

    @pytest.mark.parametrize(
        "texto",
        [
            "sin fondo",  # frase sí, referencia a imagen no
            "quita el fondo",  # sin referencia explícita a "la imagen"
            "mándame la última imagen",  # referencia sí, frase de fondo no
            "",
        ],
    )
    def test_ultima_sin_ambas_condiciones_es_false(self, texto):
        assert c.es_comando_bg_remove_ultima(texto) is False


# ─────────────────────────────────────────────────────────────────────────────
# Parser: video con avatar (HeyGen) — se chequea ANTES del video genérico
# ─────────────────────────────────────────────────────────────────────────────
class TestVideoAvatar:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("video con avatar diciendo: Hola a todos", "Hola a todos"),
            ("video presentador: Bienvenidos", "Bienvenidos"),
            ("avatar dice: Compra ya", "Compra ya"),
            ("hazme un video con presentadora narrando el reporte", "el reporte"),
        ],
    )
    def test_detecta_y_extrae_guion(self, texto, esperado):
        assert c.es_comando_video_avatar(texto) is True
        assert c.parsear_video_avatar(texto) == {"texto": esperado}

    @pytest.mark.parametrize("texto", ["video con avatar", "video de un perro corriendo", ""])
    def test_sin_guion_o_sin_avatar_es_false(self, texto):
        assert c.es_comando_video_avatar(texto) is False

    def test_none_no_falla(self):
        assert c.es_comando_video_avatar(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Parser: video genérico (Replicate)
# ─────────────────────────────────────────────────────────────────────────────
class TestVideoGenerico:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("dona video un perro corriendo", "un perro corriendo"),
            ("hazme un video de un gato", "un gato"),
            ("video: paisaje de montaña", "paisaje de montaña"),
        ],
    )
    def test_detecta_y_extrae_prompt(self, texto, esperado):
        assert c.es_comando_video(texto) is True
        assert c.parsear_video(texto) == {"prompt": esperado}

    def test_avatar_no_cuenta_como_video_generico(self):
        # El avatar es más específico y se resuelve antes: el genérico lo excluye.
        texto = "video con avatar diciendo: x"
        assert c.es_comando_video_avatar(texto) is True
        assert c.es_comando_video(texto) is False

    @pytest.mark.parametrize("texto", ["video", "quiero un café", ""])
    def test_sin_cuerpo_o_no_video_es_false(self, texto):
        assert c.es_comando_video(texto) is False

    def test_none_no_falla(self):
        assert c.es_comando_video(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Parser: documentos (factura / presupuesto / recibo) con alias → tipo canónico
# ─────────────────────────────────────────────────────────────────────────────
class TestDocumento:
    @pytest.mark.parametrize(
        "texto,tipo",
        [
            ("dona factura para Juan 500 por consultoria", "factura"),
            ("hazme un recibo de 200 a Maria", "recibo"),
            ("presupuesto para limpiar oficina", "presupuesto"),
            ("cotización: diseño web", "presupuesto"),  # alias → presupuesto
            ("invoice: web design", "factura"),  # alias inglés → factura
            ("quote: kitchen remodel", "presupuesto"),
        ],
    )
    def test_detecta_tipo_canonico_y_cuerpo(self, texto, tipo):
        assert c.es_comando_documento(texto) is True
        parsed = c.parsear_documento(texto)
        assert parsed["tipo"] == tipo
        assert parsed["cuerpo"]  # cuerpo no vacío

    @pytest.mark.parametrize(
        "texto",
        [
            "factura",  # sustantivo suelto sin cuerpo ni preposición
            "invoice for Bob",  # "for" no está en la lista de preposiciones ES
            "hola cómo estás",
            "",
        ],
    )
    def test_sin_cuerpo_valido_es_false(self, texto):
        assert c.es_comando_documento(texto) is False

    def test_none_no_falla(self):
        assert c.es_comando_documento(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Parser: voz (ElevenLabs) — varios formatos, primero-que-matchea gana
# ─────────────────────────────────────────────────────────────────────────────
class TestVoz:
    @pytest.mark.parametrize(
        "texto,esperado",
        [
            ("audio: hola mundo", "hola mundo"),
            ("lee esto en voz alta: bienvenidos", "bienvenidos"),
            ("hazme un audio de saludo de cumpleaños", "saludo de cumpleaños"),
            ("di: buenos dias", "buenos dias"),
            ("léeme esta frase importante", "esta frase importante"),
            ("convierte esto a audio: prueba", "prueba"),
        ],
    )
    def test_detecta_y_extrae_texto(self, texto, esperado):
        assert c.es_comando_voz(texto) is True
        assert c.parsear_voz(texto) == {"texto": esperado}

    @pytest.mark.parametrize("texto", ["audio sin dos puntos", "hola mundo", ""])
    def test_sin_formato_valido_es_false(self, texto):
        assert c.es_comando_voz(texto) is False

    def test_none_no_falla(self):
        assert c.es_comando_voz(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Detección "sin sujeto": intención de imagen pero falta el qué
# ─────────────────────────────────────────────────────────────────────────────
class TestSolicitudImagenSinSujeto:
    @pytest.mark.parametrize(
        "texto",
        ["genera una imagen", "dona imagen", "dibuja", "hazme una foto"],
    )
    def test_intencion_sin_sujeto_es_true(self, texto):
        assert c.es_solicitud_imagen_sin_sujeto(texto) is True

    @pytest.mark.parametrize(
        "texto",
        ["imagen de un gato", "dona imagen de gato", "dibuja un perro astronauta"],
    )
    def test_con_sujeto_no_dispara(self, texto):
        # Si ya es un comando de imagen completo, NO es "sin sujeto".
        assert c.es_comando_imagen(texto) is True
        assert c.es_solicitud_imagen_sin_sujeto(texto) is False

    @pytest.mark.parametrize("texto", ["hola", "", None])
    def test_texto_no_relacionado_es_false(self, texto):
        assert c.es_solicitud_imagen_sin_sujeto(texto) is False


# ─────────────────────────────────────────────────────────────────────────────
# Confirmar / cancelar — set amplio vs. inequívoco
# ─────────────────────────────────────────────────────────────────────────────
class TestConfirmarCancelar:
    @pytest.mark.parametrize("texto", ["confirmar", "si", "sí", "dale", "ok", "confirmo", "dona confirmar"])
    def test_confirmar_amplio(self, texto):
        assert c.es_comando_confirmar(texto) is True

    @pytest.mark.parametrize("texto", ["cancelar", "no", "dona cancelar", "dona no"])
    def test_cancelar_amplio(self, texto):
        assert c.es_comando_cancelar(texto) is True

    @pytest.mark.parametrize(
        "texto,es_conf",
        [("confirmar", True), ("confirmo", True), ("dona confirmar", True),
         ("si", False), ("sí", False), ("dale", False), ("ok", False)],
    )
    def test_confirmar_inequivoco_solo_tokens_claros(self, texto, es_conf):
        # "sí"/"ok" son ambiguos (podrían responder a otra cosa) → NO inequívocos.
        assert c.es_confirmar_inequivoco(texto) is es_conf

    @pytest.mark.parametrize(
        "texto,es_canc",
        [("cancelar", True), ("dona cancelar", True), ("no", False), ("dona no", False)],
    )
    def test_cancelar_inequivoco_solo_tokens_claros(self, texto, es_canc):
        assert c.es_cancelar_inequivoco(texto) is es_canc

    def test_confirmar_normaliza_mayusculas_y_espacios(self):
        assert c.es_comando_confirmar("  CONFIRMAR  ") is True

    @pytest.mark.parametrize("f", [c.es_comando_confirmar, c.es_comando_cancelar,
                                   c.es_confirmar_inequivoco, c.es_cancelar_inequivoco])
    def test_none_no_falla(self, f):
        assert f(None) is False


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de render
# ─────────────────────────────────────────────────────────────────────────────
class TestFmtMoneda:
    @pytest.mark.parametrize(
        "valor,moneda,esperado",
        [
            (1234.5, "USD", "$1,234.50"),
            (1000, "EUR", "€1,000.00"),
            (50, "GBP", "£50.00"),
            (99.9, "MXN", "$99.90"),
        ],
    )
    def test_simbolo_y_formato_miles(self, valor, moneda, esperado):
        assert c._fmt_moneda(valor, moneda) == esperado

    def test_moneda_desconocida_sin_simbolo(self):
        assert c._fmt_moneda(10, "ZZZ") == "10.00"

    @pytest.mark.parametrize("valor", [None, "no-numero"])
    def test_valor_no_numerico_degrada_a_cero(self, valor):
        # Con símbolo (USD) y valor inválido → "$0.00" (nunca revienta).
        assert c._fmt_moneda(valor, "USD") == "$0.00"


class TestLineaReemplazo:
    def test_sin_reemplazo_devuelve_vacio(self):
        assert c._linea_reemplazo({}) == ""

    def test_con_reemplazo_incluye_etiqueta(self):
        linea = c._linea_reemplazo({"reemplazo": "video de un gato"})
        assert "video de un gato" in linea
        assert linea.endswith("\n\n")


# ─────────────────────────────────────────────────────────────────────────────
# Renderers de preview — imagen
# ─────────────────────────────────────────────────────────────────────────────
def _preview_imagen(**over):
    base = {
        "costo_creditos": 3, "saldo_actual": 10, "alcanza": True,
        "calidad": "standard", "aspect_ratio": "1:1", "ttl_min": 15,
        "prompt": "un gato", "idea_usuario": "un gato",
    }
    base.update(over)
    return base


class TestTextoPreviewImagen:
    def test_muestra_idea_costo_y_confirmar(self):
        out = c.texto_preview(_preview_imagen())
        assert "un gato" in out
        assert "3 créditos" in out
        assert "confirmar" in out.lower()

    def test_sin_saldo_muestra_recargar(self):
        out = c.texto_preview(_preview_imagen(alcanza=False, saldo_actual=1))
        assert "recargar" in out.lower()
        assert "confirmar para generar" not in out.lower()

    def test_prompt_optimizado_distinto_se_muestra(self):
        out = c.texto_preview(_preview_imagen(prompt_optimizado="un gato siamés fotorrealista 4k"))
        assert "optimizado" in out.lower()
        assert "siamés" in out

    def test_prompt_optimizado_igual_no_duplica(self):
        out = c.texto_preview(_preview_imagen(prompt_optimizado="un gato"))
        assert "optimizado" not in out.lower()

    def test_reemplazo_se_prepende(self):
        out = c.texto_preview(_preview_imagen(reemplazo="video anterior"))
        assert out.startswith("🔄")
        assert "video anterior" in out

    def test_imagen_ajustada_tiene_header_reajuste(self):
        out = c.texto_imagen_ajustada(_preview_imagen())
        assert out.startswith("🔁")


# ─────────────────────────────────────────────────────────────────────────────
# Renderers de preview — voz
# ─────────────────────────────────────────────────────────────────────────────
def _preview_voz(**over):
    base = {"costo_creditos": 1, "saldo_actual": 5, "alcanza": True,
            "chars": 20, "ttl_min": 10, "texto": "hola mundo"}
    base.update(over)
    return base


class TestTextoPreviewVoz:
    def test_muestra_texto_y_chars(self):
        out = c.texto_voz_preview(_preview_voz())
        assert "hola mundo" in out
        assert "20 caracteres" in out

    def test_trunca_texto_largo_con_elipsis(self):
        out = c.texto_voz_preview(_preview_voz(texto="a" * 200, chars=200))
        assert "..." in out

    def test_sin_saldo_muestra_recargar(self):
        out = c.texto_voz_preview(_preview_voz(alcanza=False, saldo_actual=0))
        assert "recargar" in out.lower()

    def test_voz_ajustada_tiene_header_reajuste(self):
        out = c.texto_voz_ajustada(_preview_voz())
        assert out.startswith("🔁")


# ─────────────────────────────────────────────────────────────────────────────
# Renderers de preview — documento
# ─────────────────────────────────────────────────────────────────────────────
def _preview_doc(**over):
    base = {"tipo": "factura", "costo_creditos": 2, "saldo_actual": 9,
            "alcanza": True, "ttl_min": 10, "moneda": "USD", "total": 232}
    base.update(over)
    return base


class TestTextoPreviewDocumento:
    def test_muestra_total_y_cliente(self):
        out = c.texto_documento_preview(_preview_doc(cliente="Juan", nombre_negocio="ACME"))
        assert "$232.00" in out
        assert "Juan" in out
        assert "ACME" in out

    def test_con_items_e_impuesto(self):
        out = c.texto_documento_preview(_preview_doc(
            items=[{"cantidad": 2, "descripcion": "Hora consultoría", "subtotal": 200}],
            subtotal=200, impuesto=32,
        ))
        assert "Hora consultoría" in out
        assert "Impuesto" in out
        assert "$32.00" in out

    def test_muchos_items_muestra_y_mas(self):
        items = [{"cantidad": 1, "descripcion": f"item {i}", "subtotal": 10} for i in range(9)]
        out = c.texto_documento_preview(_preview_doc(items=items, subtotal=90, total=90))
        assert "y 3 más" in out  # muestra 6, resto colapsa (9 - 6 = 3)

    def test_sin_impuesto_no_muestra_linea(self):
        out = c.texto_documento_preview(_preview_doc(total=50))
        assert "Impuesto" not in out

    def test_sin_saldo_muestra_recargar(self):
        out = c.texto_documento_preview(_preview_doc(alcanza=False, saldo_actual=0))
        assert "recargar" in out.lower()

    @pytest.mark.parametrize("tipo", ["factura", "presupuesto", "recibo"])
    def test_todos_los_tipos_renderizan(self, tipo):
        out = c.texto_documento_preview(_preview_doc(tipo=tipo))
        assert tipo in out


# ─────────────────────────────────────────────────────────────────────────────
# Renderers de preview — video genérico
# ─────────────────────────────────────────────────────────────────────────────
def _preview_video(**over):
    base = {"costo_creditos": 5, "saldo_actual": 10, "alcanza": True,
            "ttl_min": 15, "modelo": "owner/model:v1", "duration_s": 10,
            "aspect_ratio": "16:9", "idea_usuario": "un perro", "prompt": "un perro"}
    base.update(over)
    return base


class TestTextoPreviewVideo:
    def test_muestra_modelo_duracion_y_formato(self):
        out = c.texto_video_preview(_preview_video())
        assert "model" in out  # nombre corto del modelo
        assert "10s" in out
        assert "horizontal" in out  # 16:9 → etiqueta amigable

    def test_con_imagen_referencia_titulo_distinto(self):
        out = c.texto_video_preview(_preview_video(image_url="http://x/img.png"))
        assert "referencia" in out

    def test_sin_imagen_titulo_simple(self):
        out = c.texto_video_preview(_preview_video())
        assert "referencia" not in out

    def test_prompt_optimizado_distinto_se_muestra(self):
        out = c.texto_video_preview(_preview_video(prompt_optimizado="un perro corriendo en cámara lenta"))
        assert "optimizado" in out.lower()

    def test_sin_saldo_muestra_recargar(self):
        out = c.texto_video_preview(_preview_video(alcanza=False, saldo_actual=1))
        assert "recargar" in out.lower()

    def test_video_ajustado_tiene_header_reajuste(self):
        out = c.texto_video_ajustado(_preview_video())
        assert out.startswith("🔁")


# ─────────────────────────────────────────────────────────────────────────────
# Renderers de preview — video con avatar
# ─────────────────────────────────────────────────────────────────────────────
def _preview_avatar(**over):
    base = {"costo_creditos": 4, "saldo_actual": 9, "alcanza": True,
            "ttl_min": 10, "texto": "hola", "chars": 4}
    base.update(over)
    return base


class TestTextoPreviewVideoAvatar:
    def test_muestra_texto_y_chars(self):
        out = c.texto_video_avatar_preview(_preview_avatar())
        assert "hola" in out
        assert "4 caracteres" in out

    def test_sin_configurar_avisa_placeholder(self):
        out = c.texto_video_avatar_preview(_preview_avatar(sin_configurar=True))
        assert "HeyGen no está configurado" in out

    def test_trunca_texto_largo(self):
        out = c.texto_video_avatar_preview(_preview_avatar(texto="b" * 200, chars=200))
        assert "..." in out

    def test_sin_saldo_muestra_recargar(self):
        out = c.texto_video_avatar_preview(_preview_avatar(alcanza=False, saldo_actual=0))
        assert "recargar" in out.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Renderers estáticos (encoladas y avisos sin argumentos variables)
# ─────────────────────────────────────────────────────────────────────────────
class TestRenderersEstaticos:
    def test_encolada_imagen_incluye_job_y_prompt(self):
        out = c.texto_encolada(42, "un gato astronauta")
        assert "#42" in out
        assert "un gato astronauta" in out

    def test_encolada_bg_remove_incluye_job(self):
        assert "#7" in c.texto_bg_remove_encolada(7)

    def test_encolada_voz_incluye_job(self):
        assert "#3" in c.texto_voz_encolada(3)

    def test_encolada_video_incluye_job(self):
        assert "#9" in c.texto_video_encolada(9)

    def test_encolada_video_avatar_incluye_job(self):
        assert "#11" in c.texto_video_avatar_encolada(11)

    def test_encolada_documento_incluye_job_y_display(self):
        out = c.texto_documento_encolada(5, "presupuesto")
        assert "#5" in out
        assert "presupuesto" in out

    def test_bg_remove_preview_alcanza_y_no(self):
        base = {"costo_creditos": 1, "saldo_actual": 5, "alcanza": True, "ttl_min": 10}
        assert "confirmar" in c.texto_bg_remove_preview(base).lower()
        assert "recargar" in c.texto_bg_remove_preview(dict(base, alcanza=False, saldo_actual=0)).lower()

    @pytest.mark.parametrize(
        "fn",
        [
            c.texto_sin_pendiente,
            c.texto_pedir_sujeto,
            c.texto_cancelada,
            c.texto_sin_nada_que_confirmar,
            c.texto_sin_nada_que_cancelar,
            c.texto_bg_remove_sin_imagen,
            c.texto_bg_remove_no_servible,
        ],
    )
    def test_avisos_estaticos_devuelven_texto_no_vacio(self, fn):
        out = fn()
        assert isinstance(out, str) and out.strip()
